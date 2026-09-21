"""纸质作业/试卷批改：布置、原卷页图、手批、错题账、考试回写总分。"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select, func, case, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import settings
from app.core.minio_client import upload_file, get_presigned_url, delete_file
from app.core.access import (
    apply_private_scope, apply_org_scope, require_resource,
    stamp_access_many, teacher_names,
)
from app.models.teacher import Teacher
from app.models.grading import (
    GradingAssignment, PaperSubmission, SubmissionPage, SubmissionAnswer, WrongQuestionLog,
)
from app.models.homework import HomeworkPaper, HomeworkQuestion, HomeworkType
from app.models.question import Question
from app.models.student import Student, ExamResult, EntryMethod
from app.models.textbook import ParseStatus

logger = logging.getLogger(__name__)

_WRONG_VERDICTS = {"wrong", "partial", "blank"}
_VALID_VERDICTS = {"correct", "partial", "wrong", "blank"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_PDF_MAX_PAGES = 40


def infer_question_type(q: HomeworkQuestion) -> str:
    if q.question_type:
        return q.question_type
    if q.options:
        return "single_choice"
    return "short_answer"


def _paper_type(paper: HomeworkPaper) -> str:
    return getattr(paper.paper_type, "value", paper.paper_type) or HomeworkType.homework.value


def _is_exam(paper: HomeworkPaper) -> bool:
    return _paper_type(paper) == HomeworkType.exam.value


def _q_out(q: HomeworkQuestion) -> dict:
    return {
        "id": q.id,
        "sort_order": q.sort_order,
        "content": q.content,
        "options": q.options,
        "answer": q.answer,
        "question_type": infer_question_type(q),
        "score": q.score,
        "question_id": q.question_id,
        "source": q.source,
    }


def expand_upload(filename: str, data: bytes) -> list[tuple[bytes, str, str]]:
    """图片原样；PDF 按页渲染为 PNG。返回 (bytes, content_type, file_name)。"""
    name = filename or "page.jpg"
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            n = len(doc)
            if n > _PDF_MAX_PAGES:
                raise ValueError(f"PDF 超过 {_PDF_MAX_PAGES} 页，请拆分后上传")
            stem = Path(name).stem
            out: list[tuple[bytes, str, str]] = []
            for i in range(n):
                pix = doc[i].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                out.append((pix.tobytes("png"), "image/png", f"{stem}-p{i + 1}.png"))
            return out
        finally:
            doc.close()
    if ext and ext not in _IMAGE_EXTS:
        raise ValueError("仅支持图片（jpg/png/webp）或 PDF")
    ctype = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
    }.get(ext, "image/jpeg")
    return [(data, ctype, name)]


async def _ensure_teacher(db: AsyncSession, teacher: Teacher | int) -> Teacher:
    if isinstance(teacher, Teacher):
        return teacher
    t = await db.get(Teacher, int(teacher))
    if not t:
        raise ValueError("用户不存在")
    from app.services.rbac_service import load_rbac
    await load_rbac(db, t)
    return t


async def _paper_or_404(db: AsyncSession, paper_id: int, teacher: Teacher | int) -> HomeworkPaper:
    teacher = await _ensure_teacher(db, teacher)
    paper = (await db.execute(
        select(HomeworkPaper)
        .where(HomeworkPaper.id == paper_id)
        .options(selectinload(HomeworkPaper.questions))
    )).scalar_one_or_none()
    if not paper:
        raise ValueError("作业/试卷不存在")
    try:
        await require_resource(db, teacher, paper, "homework", detail="作业/试卷不存在")
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise ValueError(str(e.detail))
        raise
    return paper


async def _assignment_or_404(
    db: AsyncSession, assignment_id: int, teacher: Teacher | int,
    *, edit: bool = False, delete: bool = False,
) -> GradingAssignment:
    teacher = await _ensure_teacher(db, teacher)
    row = (await db.execute(
        select(GradingAssignment)
        .where(GradingAssignment.id == assignment_id)
        .options(
            selectinload(GradingAssignment.paper).selectinload(HomeworkPaper.questions),
            selectinload(GradingAssignment.submissions).selectinload(PaperSubmission.pages),
            selectinload(GradingAssignment.submissions).selectinload(PaperSubmission.answers),
            selectinload(GradingAssignment.submissions).selectinload(PaperSubmission.student),
        )
    )).scalar_one_or_none()
    if not row:
        raise ValueError("布置记录不存在")
    try:
        await require_resource(
            db, teacher, row, "grading", edit=edit, delete=delete, detail="布置记录不存在",
        )
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise ValueError(str(e.detail))
        raise
    return row


async def _bump_wrong_count(db: AsyncSession, question_id: int | None, delta: int):
    if not question_id or delta == 0:
        return
    q = await db.get(Question, question_id)
    if q:
        q.wrong_count = max(0, int(q.wrong_count or 0) + delta)


async def _sync_wrong_log(
    db: AsyncSession,
    assignment: GradingAssignment,
    submission: PaperSubmission,
    answer: SubmissionAnswer,
):
    is_wrong = (answer.verdict or "") in _WRONG_VERDICTS
    log = (await db.execute(
        select(WrongQuestionLog).where(WrongQuestionLog.submission_answer_id == answer.id)
    )).scalar_one_or_none()
    if is_wrong:
        if log:
            log.is_blank = answer.verdict == "blank"
            log.question_id = answer.question_id
            return
        db.add(WrongQuestionLog(
            teacher_id=assignment.teacher_id,
            student_id=submission.student_id,
            assignment_id=assignment.id,
            paper_id=assignment.paper_id,
            paper_question_id=answer.paper_question_id,
            question_id=answer.question_id,
            submission_answer_id=answer.id,
            is_blank=answer.verdict == "blank",
        ))
        await _bump_wrong_count(db, answer.question_id, 1)
        return
    if log:
        await _bump_wrong_count(db, log.question_id, -1)
        await db.delete(log)


async def _ensure_answers(
    db: AsyncSession, submission: PaperSubmission, questions: list[HomeworkQuestion],
):
    if not _rel_loaded(submission, "answers"):
        existing = list((await db.execute(
            select(SubmissionAnswer).where(SubmissionAnswer.submission_id == submission.id)
        )).scalars().all())
        set_committed_value(submission, "answers", existing)
    have = {a.paper_question_id for a in (submission.answers or [])}
    for q in questions:
        if q.id in have:
            continue
        a = SubmissionAnswer(
            submission_id=submission.id,
            paper_question_id=q.id,
            question_id=q.question_id,
            max_score=float(q.score) if q.score is not None else None,
        )
        db.add(a)
        submission.answers.append(a)
    await db.flush()


def _refresh_submission(submission: PaperSubmission, questions: list[HomeworkQuestion], is_exam: bool):
    answers = list(submission.answers) if _rel_loaded(submission, "answers") else []
    pages = list(submission.pages) if _rel_loaded(submission, "pages") else []
    n = len(questions)
    graded = sum(1 for a in answers if a.verdict)
    if not pages:
        submission.status = "pending"
    elif n and graded >= n:
        submission.status = "graded"
    else:
        submission.status = "submitted"
    if is_exam:
        submission.full_score = sum(float(q.score or 0) for q in questions) or submission.full_score
        if graded:
            submission.total_score = round(sum(float(a.score or 0) for a in answers if a.verdict), 2)
        else:
            submission.total_score = None
    else:
        submission.full_score = None
        submission.total_score = None


async def _refresh_assignment(db: AsyncSession, assignment: GradingAssignment):
    subs = list((await db.execute(
        select(PaperSubmission)
        .where(PaperSubmission.assignment_id == assignment.id)
        .options(selectinload(PaperSubmission.pages))
    )).scalars().unique().all())
    with_pages = [s for s in subs if s.pages]
    if not with_pages:
        assignment.status = "collecting"
        return
    if all(s.status == "graded" for s in with_pages):
        assignment.status = "done"
    else:
        assignment.status = "grading"


async def _sync_exam_result(
    db: AsyncSession, assignment: GradingAssignment, paper: HomeworkPaper, submission: PaperSubmission,
):
    if not _is_exam(paper) or submission.status != "graded":
        return
    if submission.total_score is None:
        return
    row = (await db.execute(
        select(ExamResult).where(
            ExamResult.teacher_id == assignment.teacher_id,
            ExamResult.student_id == submission.student_id,
            ExamResult.subject_id == assignment.subject_id,
            ExamResult.exam_name == assignment.title,
        )
    )).scalar_one_or_none()
    full = float(submission.full_score or 100)
    if row:
        row.score = float(submission.total_score)
        row.full_score = full
        row.entry_method = EntryMethod.image
        return
    db.add(ExamResult(
        student_id=submission.student_id,
        teacher_id=assignment.teacher_id,
        subject_id=assignment.subject_id,
        exam_name=assignment.title,
        score=float(submission.total_score),
        full_score=full,
        entry_method=EntryMethod.image,
        remark="批改模块回写",
    ))


async def _roster(db: AsyncSession, assignment: GradingAssignment) -> list[Student]:
    if getattr(assignment, "class_id", None):
        q = select(Student).where(
            Student.class_id == assignment.class_id,
            Student.grade_id == assignment.grade_id,
        )
    else:
        q = select(Student).where(Student.grade_id == assignment.grade_id)
        if assignment.class_name:
            q = q.where(Student.class_name == assignment.class_name)
    return list((await db.execute(q.order_by(Student.class_name, Student.student_no))).scalars().all())


def _rel_loaded(obj, name: str) -> bool:
    """异步会话里未预加载的 relationship 不能直接访问，否则会 MissingGreenlet。"""
    if obj is None:
        return False
    try:
        return name not in sa_inspect(obj).unloaded
    except Exception:
        return False


def _student_row(stu: Student, sub: PaperSubmission | None, qcount: int) -> dict:
    pages = list(sub.pages) if sub and _rel_loaded(sub, "pages") else []
    answers = list(sub.answers) if sub and _rel_loaded(sub, "answers") else []
    graded = sum(1 for a in answers if a.verdict)
    return {
        "student_id": stu.id,
        "name": stu.name,
        "student_no": stu.student_no,
        "class_name": stu.class_name,
        "submission_id": sub.id if sub else None,
        "status": sub.status if sub else "pending",
        "page_count": len(pages),
        "graded_count": graded,
        "question_count": qcount,
        "total_score": sub.total_score if sub else None,
        "full_score": sub.full_score if sub else None,
    }


def _counts(assignment: GradingAssignment, roster_n: int) -> tuple[int, int, int]:
    if not _rel_loaded(assignment, "submissions"):
        return roster_n, 0, 0
    submitted = 0
    graded = 0
    for s in assignment.submissions or []:
        pages = list(s.pages) if _rel_loaded(s, "pages") else []
        if pages:
            submitted += 1
        if s.status == "graded":
            graded += 1
    return roster_n, submitted, graded


def _assignment_out(a: GradingAssignment, roster_n: int | None = None) -> dict:
    paper = a.paper if _rel_loaded(a, "paper") else None
    n = roster_n if roster_n is not None else 0
    student_count, submitted, graded = _counts(a, n)
    return {
        "id": a.id,
        "paper_id": a.paper_id,
        "paper_title": paper.title if paper else "",
        "paper_type": _paper_type(paper) if paper else "homework",
        "title": a.title,
        "grade_id": a.grade_id,
        "subject_id": a.subject_id,
        "class_id": getattr(a, "class_id", None),
        "class_name": a.class_name,
        "assigned_at": a.assigned_at,
        "status": a.status,
        "full_score": a.full_score,
        "student_count": student_count,
        "submitted_count": submitted,
        "graded_count": graded,
        "collect_token": getattr(a, "collect_token", None),
        "created_at": a.created_at,
        "creator_name": getattr(a, "creator_name", None),
        "is_owner": getattr(a, "is_owner", False),
        "can_edit": getattr(a, "can_edit", False),
        "can_manage_collab": getattr(a, "can_manage_collab", False),
    }


async def create_assignment(db: AsyncSession, teacher_id: int, data) -> GradingAssignment:
    paper = await _paper_or_404(db, data.paper_id, teacher_id)
    if paper.gen_status != ParseStatus.done or not paper.questions:
        raise ValueError("请选择已生成完成且含题目的作业/试卷")
    if (getattr(paper, "review_status", None) or "") != "verified":
        raise ValueError("请先在作业/考试中校对卷面后再布置")
    assigned_at = data.assigned_at or date.today()
    class_id = getattr(data, "class_id", None)
    class_name = (data.class_name or "").strip() or None
    if class_id:
        from app.services.classroom_service import get_class
        cls = await get_class(db, class_id, teacher_id)
        if not cls:
            raise ValueError("班级不存在")
        class_name = cls.name
        data.grade_id = cls.grade_id
    dup_q = select(GradingAssignment).where(
        GradingAssignment.teacher_id == teacher_id,
        GradingAssignment.paper_id == paper.id,
        GradingAssignment.assigned_at == assigned_at,
    )
    if class_id:
        dup_q = dup_q.where(GradingAssignment.class_id == class_id)
    else:
        dup_q = dup_q.where(GradingAssignment.class_name == class_name)
    dup = (await db.execute(dup_q)).scalar_one_or_none()
    if dup:
        raise ValueError("同一试卷、班级和日期已布置过")
    is_exam = _is_exam(paper)
    full = sum(float(q.score or 0) for q in paper.questions) if is_exam else None
    row = GradingAssignment(
        teacher_id=teacher_id,
        paper_id=paper.id,
        grade_id=data.grade_id,
        subject_id=data.subject_id,
        class_id=class_id,
        class_name=class_name,
        title=(data.title or "").strip() or paper.title,
        assigned_at=assigned_at,
        status="collecting",
        full_score=full,
        collect_token=secrets.token_urlsafe(16),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    set_committed_value(row, "paper", paper)
    set_committed_value(row, "submissions", [])
    return row


async def list_assignments(
    db: AsyncSession, teacher_id: Teacher | int,
    grade_id: int | None = None, subject_id: int | None = None, class_name: str | None = None,
) -> list[dict]:
    teacher = await _ensure_teacher(db, teacher_id)
    q = (
        select(GradingAssignment)
        .options(
            selectinload(GradingAssignment.paper),
            selectinload(GradingAssignment.submissions).selectinload(PaperSubmission.pages),
        )
        .order_by(GradingAssignment.assigned_at.desc(), GradingAssignment.id.desc())
    )
    q = await apply_private_scope(q, GradingAssignment, db, teacher, "grading")
    if grade_id:
        q = q.where(GradingAssignment.grade_id == grade_id)
    if subject_id:
        q = q.where(GradingAssignment.subject_id == subject_id)
    if class_name:
        q = q.where(GradingAssignment.class_name == class_name)
    rows = list((await db.execute(q)).scalars().all())
    await stamp_access_many(db, teacher, rows, "grading")
    out = []
    for a in rows:
        roster = await _roster(db, a)
        out.append(_assignment_out(a, len(roster)))
    return out


async def get_assignment_detail(db: AsyncSession, assignment_id: int, teacher_id: int) -> dict:
    a = await _assignment_or_404(db, assignment_id, teacher_id)
    teacher = await _ensure_teacher(db, teacher_id)
    await stamp_access_many(db, teacher, [a], "grading")
    paper = a.paper
    questions = sorted(paper.questions, key=lambda x: x.sort_order)
    qcount = len(questions)
    roster = await _roster(db, a)
    by_stu = {s.student_id: s for s in a.submissions}
    students = [_student_row(stu, by_stu.get(stu.id), qcount) for stu in roster]

    logs = (await db.execute(
        select(WrongQuestionLog).where(WrongQuestionLog.assignment_id == a.id)
    )).scalars().all()
    err_n: dict[int, int] = {}
    blank_n: dict[int, int] = {}
    for log in logs:
        err_n[log.paper_question_id] = err_n.get(log.paper_question_id, 0) + 1
        if log.is_blank:
            blank_n[log.paper_question_id] = blank_n.get(log.paper_question_id, 0) + 1
    graded_n: dict[int, int] = {}
    for sub in a.submissions:
        for ans in sub.answers:
            if ans.verdict:
                graded_n[ans.paper_question_id] = graded_n.get(ans.paper_question_id, 0) + 1

    stats = []
    for q in questions:
        g = graded_n.get(q.id, 0)
        e = err_n.get(q.id, 0)
        stats.append({
            "paper_question_id": q.id,
            "sort_order": q.sort_order,
            "content": q.content,
            "question_id": q.question_id,
            "error_count": e,
            "blank_count": blank_n.get(q.id, 0),
            "graded_count": g,
            "error_rate": round(e / g, 4) if g else 0.0,
        })

    data = _assignment_out(a, len(roster))
    data["questions"] = [_q_out(q) for q in questions]
    data["question_stats"] = stats
    data["students"] = students
    return data


async def delete_assignment(db: AsyncSession, assignment_id: int, teacher_id: int):
    a = await _assignment_or_404(db, assignment_id, teacher_id, delete=True)
    logs = (await db.execute(
        select(WrongQuestionLog).where(WrongQuestionLog.assignment_id == a.id)
    )).scalars().all()
    by_q: dict[int, int] = {}
    for log in logs:
        if log.question_id:
            by_q[log.question_id] = by_q.get(log.question_id, 0) + 1
    for qid, n in by_q.items():
        await _bump_wrong_count(db, qid, -n)
    objects: list[str] = []
    for sub in a.submissions:
        for p in sub.pages:
            objects.append(p.object_name)
    for log in logs:
        await db.delete(log)
    await db.flush()
    await db.delete(a)
    await db.flush()
    for name in objects:
        delete_file(settings.MINIO_BUCKET_GRADING, name)


async def get_or_create_submission(
    db: AsyncSession, assignment_id: int, student_id: int, teacher_id: int,
) -> tuple[GradingAssignment, PaperSubmission, Student]:
    a = await _assignment_or_404(db, assignment_id, teacher_id)
    stu = (await db.execute(
        select(Student).where(Student.id == student_id)
    )).scalar_one_or_none()
    if not stu:
        raise ValueError("学生不存在")
    if stu.grade_id != a.grade_id:
        raise ValueError("学生年级与本次布置不一致")
    if a.class_id and stu.class_id and stu.class_id != a.class_id:
        raise ValueError("该学生不在本次布置的班级")
    sub = next((s for s in a.submissions if s.student_id == student_id), None)
    if not sub:
        sub = PaperSubmission(
            assignment_id=a.id,
            student_id=student_id,
            teacher_id=teacher_id,
            status="pending",
            full_score=a.full_score,
        )
        db.add(sub)
        await db.flush()
        a.submissions.append(sub)
        set_committed_value(sub, "pages", [])
        set_committed_value(sub, "answers", [])
        set_committed_value(sub, "student", stu)
    set_committed_value(sub, "assignment", a)
    questions = sorted(a.paper.questions, key=lambda x: x.sort_order)
    await _ensure_answers(db, sub, questions)
    _refresh_submission(sub, questions, _is_exam(a.paper))
    return a, sub, stu


def _page_out(p: SubmissionPage) -> dict:
    return {
        "id": p.id,
        "page_index": p.page_index,
        "url": get_presigned_url(settings.MINIO_BUCKET_GRADING, p.object_name, expires_hours=6),
        "file_name": p.file_name,
    }


async def submission_detail(
    db: AsyncSession, assignment_id: int, student_id: int, teacher_id: int,
) -> dict:
    a, sub, stu = await get_or_create_submission(db, assignment_id, student_id, teacher_id)
    teacher = await _ensure_teacher(db, teacher_id)
    await stamp_access_many(db, teacher, [a], "grading")
    paper = a.paper
    questions = sorted(paper.questions, key=lambda x: x.sort_order)
    roster = await _roster(db, a)
    by_stu = {s.student_id: s for s in a.submissions}
    answers = []
    by_pq = {x.paper_question_id: x for x in (sub.answers or [])}
    for q in questions:
        ans = by_pq.get(q.id)
        if not ans:
            continue
        answers.append({
            "id": ans.id,
            "paper_question_id": ans.paper_question_id,
            "question_id": ans.question_id,
            "student_answer": ans.student_answer,
            "verdict": ans.verdict,
            "is_correct": ans.is_correct,
            "score": ans.score,
            "max_score": ans.max_score,
            "comment": ans.comment,
            "grade_method": ans.grade_method or "manual",
            "page_index": ans.page_index,
        })
    pages = [_page_out(p) for p in sorted(sub.pages or [], key=lambda x: x.page_index)]
    return {
        "id": sub.id,
        "assignment_id": a.id,
        "student_id": stu.id,
        "student_name": stu.name,
        "student_no": stu.student_no,
        "status": sub.status,
        "total_score": sub.total_score,
        "full_score": sub.full_score,
        "paper_type": _paper_type(paper),
        "assignment_title": a.title,
        "pages": pages,
        "answers": answers,
        "questions": [_q_out(q) for q in questions],
        "roster": [_student_row(s, by_stu.get(s.id), len(questions)) for s in roster],
        "can_edit": getattr(a, "can_edit", False),
    }


async def add_pages(
    db: AsyncSession, submission_id: int, teacher_id: int,
    files: list[tuple[str, bytes]],
) -> PaperSubmission:
    sub = (await db.execute(
        select(PaperSubmission)
        .where(PaperSubmission.id == submission_id)
        .options(
            selectinload(PaperSubmission.pages),
            selectinload(PaperSubmission.answers),
            selectinload(PaperSubmission.assignment).selectinload(GradingAssignment.paper).selectinload(HomeworkPaper.questions),
            selectinload(PaperSubmission.assignment).selectinload(GradingAssignment.submissions),
        )
    )).scalar_one_or_none()
    if not sub:
        raise ValueError("答卷不存在")
    teacher = await _ensure_teacher(db, teacher_id)
    try:
        await require_resource(db, teacher, sub.assignment, "grading", edit=True, detail="答卷不存在")
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise ValueError(str(e.detail))
        raise
    idx = max((p.page_index for p in sub.pages), default=-1) + 1
    for filename, data in files:
        for blob, ctype, fname in expand_upload(filename, data):
            ext = "png" if ctype == "image/png" else "jpg"
            object_name = f"{teacher_id}/{sub.assignment_id}/{sub.id}/{uuid.uuid4().hex}.{ext}"
            upload_file(settings.MINIO_BUCKET_GRADING, object_name, blob, ctype)
            page = SubmissionPage(
                submission_id=sub.id,
                page_index=idx,
                object_name=object_name,
                content_type=ctype,
                file_name=fname,
            )
            db.add(page)
            sub.pages.append(page)
            idx += 1
    questions = sorted(sub.assignment.paper.questions, key=lambda x: x.sort_order)
    _refresh_submission(sub, questions, _is_exam(sub.assignment.paper))
    await _refresh_assignment(db, sub.assignment)
    return sub


async def delete_page(db: AsyncSession, submission_id: int, page_id: int, teacher_id: int):
    sub = (await db.execute(
        select(PaperSubmission)
        .where(PaperSubmission.id == submission_id)
        .options(
            selectinload(PaperSubmission.pages),
            selectinload(PaperSubmission.answers),
            selectinload(PaperSubmission.assignment).selectinload(GradingAssignment.paper).selectinload(HomeworkPaper.questions),
            selectinload(PaperSubmission.assignment).selectinload(GradingAssignment.submissions),
        )
    )).scalar_one_or_none()
    if not sub:
        raise ValueError("答卷不存在")
    teacher = await _ensure_teacher(db, teacher_id)
    try:
        await require_resource(db, teacher, sub.assignment, "grading", edit=True, detail="答卷不存在")
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise ValueError(str(e.detail))
        raise
    page = next((p for p in sub.pages if p.id == page_id), None)
    if not page:
        raise ValueError("页图不存在")
    name = page.object_name
    await db.delete(page)
    await db.flush()
    remaining = sorted([p for p in sub.pages if p.id != page_id], key=lambda x: x.page_index)
    for i, p in enumerate(remaining):
        p.page_index = i
    questions = sorted(sub.assignment.paper.questions, key=lambda x: x.sort_order)
    _refresh_submission(sub, questions, _is_exam(sub.assignment.paper))
    await _refresh_assignment(db, sub.assignment)
    delete_file(settings.MINIO_BUCKET_GRADING, name)


async def reorder_pages(db: AsyncSession, submission_id: int, teacher_id: int, page_ids: list[int]):
    sub = (await db.execute(
        select(PaperSubmission)
        .where(PaperSubmission.id == submission_id)
        .options(
            selectinload(PaperSubmission.pages),
            selectinload(PaperSubmission.assignment),
        )
    )).scalar_one_or_none()
    if not sub:
        raise ValueError("答卷不存在")
    teacher = await _ensure_teacher(db, teacher_id)
    try:
        await require_resource(db, teacher, sub.assignment, "grading", edit=True, detail="答卷不存在")
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise ValueError(str(e.detail))
        raise
    by_id = {p.id: p for p in sub.pages}
    if set(page_ids) != set(by_id):
        raise ValueError("页序与现有页不匹配")
    for i, pid in enumerate(page_ids):
        by_id[pid].page_index = i


def _apply_verdict(answer: SubmissionAnswer, verdict: str | None, score: float | None, is_exam: bool):
    if verdict is None or verdict == "":
        answer.verdict = None
        answer.is_correct = None
        answer.score = None
        return
    if verdict not in _VALID_VERDICTS:
        raise ValueError("批改结果无效")
    answer.verdict = verdict
    answer.is_correct = verdict == "correct"
    if not is_exam:
        answer.score = None
        return
    max_s = float(answer.max_score or 0)
    if verdict == "correct":
        answer.score = max_s
    elif verdict in ("wrong", "blank"):
        answer.score = 0.0
    elif score is not None:
        answer.score = max(0.0, min(float(score), max_s or float(score)))
    elif answer.score is None and max_s:
        answer.score = round(max_s / 2, 2)


async def grade_answers(
    db: AsyncSession, submission_id: int, teacher_id: int, items: list,
) -> PaperSubmission:
    sub = (await db.execute(
        select(PaperSubmission)
        .where(PaperSubmission.id == submission_id)
        .options(
            selectinload(PaperSubmission.pages),
            selectinload(PaperSubmission.answers),
            selectinload(PaperSubmission.assignment).selectinload(GradingAssignment.paper).selectinload(HomeworkPaper.questions),
            selectinload(PaperSubmission.assignment).selectinload(GradingAssignment.submissions),
            selectinload(PaperSubmission.student),
        )
    )).scalar_one_or_none()
    if not sub:
        raise ValueError("答卷不存在")
    teacher = await _ensure_teacher(db, teacher_id)
    try:
        await require_resource(db, teacher, sub.assignment, "grading", edit=True, detail="答卷不存在")
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise ValueError(str(e.detail))
        raise
    a = sub.assignment
    questions = sorted(a.paper.questions, key=lambda x: x.sort_order)
    await _ensure_answers(db, sub, questions)
    by_pq = {x.paper_question_id: x for x in sub.answers}
    is_exam = _is_exam(a.paper)
    for item in items:
        pqid = item.paper_question_id
        ans = by_pq.get(pqid)
        if not ans:
            raise ValueError("题目不属于本次布置")
        _apply_verdict(ans, item.verdict, item.score, is_exam)
        if item.comment is not None:
            ans.comment = item.comment
        if item.student_answer is not None:
            ans.student_answer = item.student_answer
        if item.page_index is not None:
            ans.page_index = item.page_index
        ans.grade_method = "manual"
        await _sync_wrong_log(db, a, sub, ans)
    _refresh_submission(sub, questions, is_exam)
    await _refresh_assignment(db, a)
    await _sync_exam_result(db, a, a.paper, sub)
    return sub


async def list_wrong_questions(
    db: AsyncSession, teacher_id: int, scope: str,
    assignment_id: int | None = None, student_id: int | None = None,
    grade_id: int | None = None, subject_id: int | None = None,
) -> list[dict]:
    teacher = await _ensure_teacher(db, teacher_id)
    if scope == "bank":
        q = select(Question).where(Question.wrong_count > 0)
        q = await apply_org_scope(q, Question.teacher_id, db, teacher)
        if grade_id:
            q = q.where(Question.grade_id == grade_id)
        if subject_id:
            q = q.where(Question.subject_id == subject_id)
        rows = (await db.execute(q.order_by(Question.wrong_count.desc(), Question.id.desc()))).scalars().all()
        return [{
            "question_id": r.id,
            "content": r.content,
            "question_type": getattr(r.question_type, "value", r.question_type),
            "error_count": r.wrong_count or 0,
            "use_count": r.use_count or 0,
        } for r in rows]

    vis_q = select(GradingAssignment.id)
    vis_q = await apply_private_scope(vis_q, GradingAssignment, db, teacher, "grading")
    vis_ids = list((await db.execute(vis_q)).scalars().all())
    stmt = (
        select(
            WrongQuestionLog.student_id,
            WrongQuestionLog.assignment_id,
            WrongQuestionLog.paper_question_id,
            WrongQuestionLog.question_id,
            func.count(WrongQuestionLog.id).label("error_count"),
            func.sum(case((WrongQuestionLog.is_blank.is_(True), 1), else_=0)).label("blank_count"),
            func.max(WrongQuestionLog.created_at).label("last_at"),
        )
        .where(WrongQuestionLog.assignment_id.in_(vis_ids or [0]))
        .group_by(
            WrongQuestionLog.student_id,
            WrongQuestionLog.assignment_id,
            WrongQuestionLog.paper_question_id,
            WrongQuestionLog.question_id,
        )
    )
    if assignment_id:
        stmt = stmt.where(WrongQuestionLog.assignment_id == assignment_id)
    if student_id:
        stmt = stmt.where(WrongQuestionLog.student_id == student_id)
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    pq_ids = {r.paper_question_id for r in rows}
    as_ids = {r.assignment_id for r in rows}
    stu_ids = {r.student_id for r in rows}
    questions = {
        q.id: q for q in (await db.execute(
            select(HomeworkQuestion).where(HomeworkQuestion.id.in_(pq_ids or [-1]))
        )).scalars().all()
    }
    assignments = {
        x.id: x for x in (await db.execute(
            select(GradingAssignment).where(GradingAssignment.id.in_(as_ids or [-1]))
        )).scalars().all()
    }
    students = {
        s.id: s for s in (await db.execute(
            select(Student).where(Student.id.in_(stu_ids or [-1]))
        )).scalars().all()
    }

    if scope == "assignment":
        agg: dict[int, dict] = {}
        for r in rows:
            pq = questions.get(r.paper_question_id)
            item = agg.setdefault(r.paper_question_id, {
                "paper_question_id": r.paper_question_id,
                "question_id": r.question_id,
                "sort_order": pq.sort_order if pq else 0,
                "content": pq.content if pq else "",
                "question_type": infer_question_type(pq) if pq else None,
                "error_count": 0,
                "blank_count": 0,
                "last_at": r.last_at,
            })
            item["error_count"] += int(r.error_count or 0)
            item["blank_count"] += int(r.blank_count or 0)
            if r.last_at and (not item["last_at"] or r.last_at > item["last_at"]):
                item["last_at"] = r.last_at
        return sorted(agg.values(), key=lambda x: -x["error_count"])

    # student / default: 每位学生每题
    out = []
    for r in rows:
        pq = questions.get(r.paper_question_id)
        stu = students.get(r.student_id)
        asn = assignments.get(r.assignment_id)
        out.append({
            "student_id": r.student_id,
            "student_name": stu.name if stu else "",
            "student_no": stu.student_no if stu else "",
            "assignment_id": r.assignment_id,
            "assignment_title": asn.title if asn else "",
            "paper_question_id": r.paper_question_id,
            "question_id": r.question_id,
            "sort_order": pq.sort_order if pq else 0,
            "content": pq.content if pq else "",
            "question_type": infer_question_type(pq) if pq else None,
            "error_count": int(r.error_count or 0),
            "blank_count": int(r.blank_count or 0),
            "last_at": r.last_at,
        })
    out.sort(key=lambda x: (x.get("student_no") or "", -(x["error_count"])))
    return out


_COLLECT_MAX_FILES = 20
_COLLECT_MAX_BYTES = 20 * 1024 * 1024


async def _assignment_by_token(db: AsyncSession, token: str) -> GradingAssignment:
    tok = (token or "").strip()
    if not tok:
        raise ValueError("录入链接无效或已失效")
    row = (await db.execute(
        select(GradingAssignment)
        .where(GradingAssignment.collect_token == tok)
        .options(
            selectinload(GradingAssignment.paper),
            selectinload(GradingAssignment.submissions).selectinload(PaperSubmission.pages),
        )
    )).scalar_one_or_none()
    if not row:
        raise ValueError("录入链接无效或已失效")
    return row


async def ensure_collect_token(db: AsyncSession, assignment_id: int, teacher_id: int) -> str:
    a = await _assignment_or_404(db, assignment_id, teacher_id, edit=True)
    if not a.collect_token:
        a.collect_token = secrets.token_urlsafe(16)
        await db.flush()
    return a.collect_token


async def collect_meta(db: AsyncSession, token: str) -> dict:
    a = await _assignment_by_token(db, token)
    roster = await _roster(db, a)
    by_stu = {s.student_id: s for s in (a.submissions or [])}
    students = []
    for stu in roster:
        sub = by_stu.get(stu.id)
        pages = list(sub.pages) if sub and _rel_loaded(sub, "pages") else []
        students.append({
            "id": stu.id,
            "name": stu.name,
            "student_no": stu.student_no,
            "page_count": len(pages),
        })
    paper = a.paper if _rel_loaded(a, "paper") else None
    return {
        "title": a.title,
        "class_name": a.class_name,
        "paper_type": _paper_type(paper) if paper else "homework",
        "assigned_at": a.assigned_at,
        "students": students,
    }


async def collect_upload_pages(
    db: AsyncSession, token: str, student_id: int, files: list[tuple[str, bytes]],
) -> dict:
    if not files:
        raise ValueError("请选择图片")
    if len(files) > _COLLECT_MAX_FILES:
        raise ValueError(f"一次最多上传 {_COLLECT_MAX_FILES} 张")
    for name, data in files:
        if len(data) > _COLLECT_MAX_BYTES:
            raise ValueError(f"{name or '图片'} 超过 20MB，请压缩后重试")
    a = await _assignment_by_token(db, token)
    _a, sub, stu = await get_or_create_submission(db, a.id, student_id, a.teacher_id)
    await add_pages(db, sub.id, a.teacher_id, files)
    page_n = len(sub.pages or [])
    return {
        "student_id": stu.id,
        "student_name": stu.name,
        "page_count": page_n,
    }
