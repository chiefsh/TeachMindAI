"""课堂互动会话：教师开课堂互动、生成分享码；学生端免登录作答并回收数据。"""
import secrets
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.courseware import Courseware
from app.models.textbook import ParseStatus
from app.models.interaction import CoursewareSession, InteractionRecord
from app.api.deps import get_current_teacher

router = APIRouter(tags=["课堂互动"])


# ---------- Schemas ----------

class SessionCreate(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    id: int
    courseware_id: int
    token: str
    title: str
    is_open: bool
    record_count: int = 0
    student_count: int = 0

    class Config:
        from_attributes = True


class RecordCreate(BaseModel):
    student_name: str
    slide_index: int = 0
    component: str | None = None
    question: str | None = None
    answer: str | None = None
    is_correct: bool | None = None
    duration_ms: int | None = None


class PublicSessionOut(BaseModel):
    token: str
    title: str
    is_open: bool
    content: dict | None = None
    theme: str | None = None


# ---------- 教师端 ----------

@router.post("/coursewares/{cw_id}/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    cw_id: int,
    data: SessionCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = (await db.execute(
        select(Courseware).where(Courseware.id == cw_id, Courseware.teacher_id == teacher.id)
    )).scalar_one_or_none()
    if not cw:
        raise HTTPException(status_code=404, detail="课件不存在")
    if cw.gen_status != ParseStatus.done or not cw.content:
        raise HTTPException(status_code=400, detail="课件尚未生成完成，无法开启互动")

    session = CoursewareSession(
        teacher_id=teacher.id,
        courseware_id=cw.id,
        token=secrets.token_urlsafe(8),
        title=data.title or cw.title,
        is_open=True,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionOut.model_validate(session)


@router.get("/coursewares/{cw_id}/sessions", response_model=list[SessionOut])
async def list_sessions(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(CoursewareSession)
        .where(
            CoursewareSession.courseware_id == cw_id,
            CoursewareSession.teacher_id == teacher.id,
        )
        .order_by(CoursewareSession.created_at.desc())
    )).scalars().all()
    if not rows:
        return []

    # 一次聚合避免 N+1
    sid_list = [s.id for s in rows]
    stats_rows = (await db.execute(
        select(
            InteractionRecord.session_id,
            func.count(InteractionRecord.id),
            func.count(func.distinct(InteractionRecord.student_name)),
        )
        .where(InteractionRecord.session_id.in_(sid_list))
        .group_by(InteractionRecord.session_id)
    )).all()
    stats = {sid: (cnt or 0, stu or 0) for sid, cnt, stu in stats_rows}

    out: list[SessionOut] = []
    for s in rows:
        o = SessionOut.model_validate(s)
        o.record_count, o.student_count = stats.get(s.id, (0, 0))
        out.append(o)
    return out


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def toggle_session(
    session_id: int,
    is_open: bool,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    s = await _get_session_or_404(session_id, teacher.id, db)
    s.is_open = is_open
    await db.commit()
    await db.refresh(s)
    return SessionOut.model_validate(s)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    s = await _get_session_or_404(session_id, teacher.id, db)
    await db.delete(s)
    await db.commit()


@router.get("/sessions/{session_id}/board")
async def session_board(
    session_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """互动数据看板：按题目正确率聚合 + 按学生汇总 + 原始明细。"""
    s = await _get_session_or_404(session_id, teacher.id, db)
    rows = (await db.execute(
        select(InteractionRecord)
        .where(InteractionRecord.session_id == s.id)
        .order_by(InteractionRecord.created_at.asc())
    )).scalars().all()

    # 按题目聚合
    by_q: dict[tuple, dict] = {}
    by_student: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "correct": 0})
    students: set[str] = set()
    for r in rows:
        students.add(r.student_name)
        key = (r.slide_index, r.question or "")
        q = by_q.setdefault(key, {
            "slide_index": r.slide_index,
            "question": r.question or f"第 {r.slide_index + 1} 页互动",
            "component": r.component,
            "attempts": 0,
            "correct": 0,
        })
        q["attempts"] += 1
        if r.is_correct:
            q["correct"] += 1
        st = by_student[r.student_name]
        st["attempts"] += 1
        if r.is_correct:
            st["correct"] += 1

    questions = []
    for q in by_q.values():
        rate = round(q["correct"] / q["attempts"] * 100, 1) if q["attempts"] else 0.0
        questions.append({**q, "correct_rate": rate})
    questions.sort(key=lambda x: (x["slide_index"], x["question"]))

    student_list = [
        {"name": name, **vals,
         "correct_rate": round(vals["correct"] / vals["attempts"] * 100, 1) if vals["attempts"] else 0.0}
        for name, vals in by_student.items()
    ]
    student_list.sort(key=lambda x: x["name"])

    records = [
        {
            "id": r.id, "student_name": r.student_name, "slide_index": r.slide_index,
            "component": r.component, "question": r.question, "answer": r.answer,
            "is_correct": r.is_correct, "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

    return {
        "session": SessionOut.model_validate(s).model_dump() | {
            "record_count": len(rows), "student_count": len(students),
        },
        "summary": {
            "total_records": len(rows),
            "student_count": len(students),
            "question_count": len(questions),
        },
        "questions": questions,
        "students": student_list,
        "records": records,
    }


# ---------- 学生公开端（免登录） ----------

@router.get("/public/sessions/{token}", response_model=PublicSessionOut)
async def public_get_session(token: str, db: AsyncSession = Depends(get_db)):
    s = (await db.execute(
        select(CoursewareSession).where(CoursewareSession.token == token)
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="互动会话不存在或已结束")
    cw = (await db.execute(
        select(Courseware).where(Courseware.id == s.courseware_id)
    )).scalar_one_or_none()
    return PublicSessionOut(
        token=s.token,
        title=s.title,
        is_open=s.is_open,
        content=_public_content(cw.content if cw else None),
        theme=cw.theme if cw else None,
    )


def _public_content(content: dict | None) -> dict | None:
    """精简下发给学生端的课件内容：仅保留含互动页所需字段，去除教师讲稿等敏感信息。"""
    if not content:
        return None
    slides = []
    for i, s in enumerate(content.get("slides") or []):
        if not s.get("html"):
            continue
        slides.append({
            "pos": i,  # 在原课件中的页序（0 基），用于看板按页归类
            "type": s.get("type"),
            "title": s.get("title"),
            "html": s.get("html"),
        })
    return {"meta": {"title": (content.get("meta") or {}).get("title")}, "slides": slides}


@router.post("/public/sessions/{token}/records", status_code=201)
async def public_submit_record(
    token: str, data: RecordCreate, db: AsyncSession = Depends(get_db)
):
    s = (await db.execute(
        select(CoursewareSession).where(CoursewareSession.token == token)
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="互动会话不存在或已结束")
    if not s.is_open:
        raise HTTPException(status_code=403, detail="该互动已关闭作答")

    name = (data.student_name or "").strip()[:64] or "匿名学生"
    rec = InteractionRecord(
        session_id=s.id,
        student_name=name,
        slide_index=data.slide_index or 0,
        component=(data.component or None),
        question=(data.question or None),
        answer=(data.answer or None),
        is_correct=data.is_correct,
        duration_ms=data.duration_ms,
    )
    db.add(rec)
    await db.commit()
    return {"ok": True}


# ---------- helpers ----------

async def _get_session_or_404(session_id: int, teacher_id: int, db: AsyncSession) -> CoursewareSession:
    s = (await db.execute(
        select(CoursewareSession).where(
            CoursewareSession.id == session_id,
            CoursewareSession.teacher_id == teacher_id,
        )
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="互动会话不存在")
    return s
