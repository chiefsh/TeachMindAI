"""试题分析：导入试题 → 拆题 → 勾选 → AI 图解解析 → 查看/入库/导出。"""
import io
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from urllib.parse import quote

from app.core.database import get_db
from app.core.config import settings
from app.core.minio_client import upload_file
from app.models.teacher import Teacher
from app.models.education import Grade, Subject
from app.models.textbook import ParseStatus
from app.models.question_analysis import AnalysisSet, AnalysisQuestion
from app.schemas.question_analysis import (
    AnalysisSetOut, AnalysisSetDetail, AnalysisQuestionOut,
    ManualImportIn, AnalyzeIn, SaveToBankIn,
)
from app.api.deps import get_current_teacher, require_perm
from app.core.access import apply_private_scope, require_resource, stamp_access_many

router = APIRouter(prefix="/question-analysis", tags=["试题分析"])

ALLOWED_TYPES = {"pdf", "doc", "docx", "txt", "jpg", "jpeg", "png", "webp"}


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def _default_name(db: AsyncSession, grade_id: int, subject_id: int) -> str:
    grade = (await db.execute(select(Grade).where(Grade.id == grade_id))).scalar_one_or_none()
    subject = (await db.execute(select(Subject).where(Subject.id == subject_id))).scalar_one_or_none()
    g = grade.name if grade else "年级"
    s = subject.name if subject else "学科"
    return f"{g}_{s}_{datetime.now():%Y%m%d%H%M%S}"


async def _get_set_or_404(
    set_id: int, teacher: Teacher, db: AsyncSession, with_questions: bool = False,
    *, edit: bool = False, delete: bool = False,
) -> AnalysisSet:
    q = select(AnalysisSet).where(AnalysisSet.id == set_id)
    if with_questions:
        q = q.options(selectinload(AnalysisSet.questions))
    aset = (await db.execute(q)).scalar_one_or_none()
    return await require_resource(
        db, teacher, aset, "analysis", edit=edit, delete=delete, detail="试题批次不存在",
    )


@router.get("", response_model=dict)
async def list_sets(
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    base = select(AnalysisSet.id)
    base = await apply_private_scope(base, AnalysisSet, db, teacher, "analysis")
    if grade_id:
        base = base.where(AnalysisSet.grade_id == grade_id)
    if subject_id:
        base = base.where(AnalysisSet.subject_id == subject_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    q = (
        select(AnalysisSet, func.count(AnalysisQuestion.id))
        .outerjoin(AnalysisQuestion, AnalysisQuestion.set_id == AnalysisSet.id)
    )
    q = await apply_private_scope(q, AnalysisSet, db, teacher, "analysis")
    if grade_id:
        q = q.where(AnalysisSet.grade_id == grade_id)
    if subject_id:
        q = q.where(AnalysisSet.subject_id == subject_id)
    q = (
        q.group_by(AnalysisSet.id)
        .order_by(AnalysisSet.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).all()
    asets = [aset for aset, _ in rows]
    await stamp_access_many(db, teacher, asets, "analysis")
    items: list[AnalysisSetOut] = []
    for aset, cnt in rows:
        item = AnalysisSetOut.model_validate(aset)
        item.question_count = cnt or 0
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/import-manual", response_model=AnalysisSetDetail, status_code=201)
async def import_manual(
    data: ManualImportIn,
    teacher: Teacher = Depends(require_perm("analysis.create")),
    db: AsyncSession = Depends(get_db),
):
    """富文本/纯文本录入：默认调用 LLM 拆题（失败回退按题号拆分）。"""
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请输入试题内容")

    from app.services.ai_service import _get_default_llm, parse_questions_from_text
    from app.services.file_service import _fallback_split_dicts, _coerce_qtype, _coerce_difficulty
    from app.services.question_bank_service import strip_stem_number

    parsed: list[dict] = []
    cfg = await _get_default_llm(teacher.id, db)
    if cfg:
        try:
            parsed = await parse_questions_from_text(cfg, text)
        except Exception:
            parsed = []
    if not parsed:
        parsed = _fallback_split_dicts(text)

    name = (data.name or "").strip() or await _default_name(db, data.grade_id, data.subject_id)
    aset = AnalysisSet(
        teacher_id=teacher.id, grade_id=data.grade_id, subject_id=data.subject_id,
        name=name, source_type="manual", parse_status=ParseStatus.done,
    )
    db.add(aset)
    await db.flush()

    seq = 0
    aqs: list[AnalysisQuestion] = []
    for item in parsed:
        content = strip_stem_number(item.get("content") or "")
        if not content:
            continue
        seq += 1
        aq = AnalysisQuestion(
            set_id=aset.id, teacher_id=teacher.id, seq=seq,
            content=content[:8000], options=item.get("options") or None,
            answer=(item.get("answer") or None),
            question_type=_coerce_qtype(item.get("question_type")),
            difficulty=_coerce_difficulty(item.get("difficulty")),
        )
        db.add(aq)
        aqs.append(aq)
    if seq == 0:
        raise HTTPException(status_code=400, detail="未能识别出有效题目，请检查输入")

    from app.services.question_bank_service import attach_bank_analysis, upsert_payloads
    await upsert_payloads(
        db,
        teacher_id=teacher.id,
        subject_id=data.subject_id,
        grade_id=data.grade_id,
        items=parsed,
    )
    await attach_bank_analysis(db, teacher.id, aqs)

    await db.commit()
    aset = await _get_set_or_404(aset.id, teacher, db, with_questions=True)
    detail = AnalysisSetDetail.model_validate(aset)
    detail.question_count = len(aset.questions)
    return detail


@router.post("/import-file", response_model=AnalysisSetOut, status_code=201)
async def import_file(
    file: UploadFile = File(...),
    grade_id: int = Form(...),
    subject_id: int = Form(...),
    name: Optional[str] = Form(None),
    teacher: Teacher = Depends(require_perm("analysis.create")),
    db: AsyncSession = Depends(get_db),
):
    ext = _ext(file.filename or "")
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式，支持：{', '.join(sorted(ALLOWED_TYPES))}")

    raw = await file.read()
    object_name = f"{teacher.id}/analysis/{uuid.uuid4()}.{ext}"
    upload_file(settings.MINIO_BUCKET_QUESTIONS, object_name, raw, file.content_type or "application/octet-stream")

    set_name = (name or "").strip() or await _default_name(db, grade_id, subject_id)
    aset = AnalysisSet(
        teacher_id=teacher.id, grade_id=grade_id, subject_id=subject_id,
        name=set_name, source_type="image" if ext in ("jpg", "jpeg", "png", "webp") else "file",
        source_file_path=object_name, parse_status=ParseStatus.pending,
    )
    db.add(aset)
    await db.flush()
    await db.refresh(aset)
    await db.commit()

    from app.tasks.file_tasks import parse_analysis_file_task
    task = parse_analysis_file_task.delay(aset.id)
    aset.task_id = task.id
    await db.commit()

    out = AnalysisSetOut.model_validate(aset)
    out.question_count = 0
    return out


@router.get("/{set_id}", response_model=AnalysisSetDetail)
async def get_set(
    set_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher, db, with_questions=True)
    await stamp_access_many(db, teacher, [aset], "analysis")
    detail = AnalysisSetDetail.model_validate(aset)
    detail.question_count = len(aset.questions)
    return detail


@router.get("/{set_id}/status")
async def get_status(
    set_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher, db, with_questions=True)
    qs = aset.questions
    return {
        "parse_status": aset.parse_status.value,
        "question_count": len(qs),
        "analysis": {
            "pending": sum(1 for q in qs if q.selected and q.analysis_status == ParseStatus.pending),
            "processing": sum(1 for q in qs if q.analysis_status == ParseStatus.processing),
            "done": sum(1 for q in qs if q.selected and q.analysis_status == ParseStatus.done),
            "failed": sum(1 for q in qs if q.selected and q.analysis_status == ParseStatus.failed),
        },
    }


@router.post("/{set_id}/reparse", response_model=AnalysisSetOut)
async def reparse(
    set_id: int,
    teacher: Teacher = Depends(require_perm("analysis.edit")),
    db: AsyncSession = Depends(get_db),
):
    """重新解析：清空已拆题目并重新拆题（仅文件/图片导入的批次可用）。"""
    aset = await _get_set_or_404(set_id, teacher, db, edit=True)
    if aset.source_type == "manual" or not aset.source_file_path:
        raise HTTPException(status_code=400, detail="该批次没有可重新解析的源文件")

    await db.execute(delete(AnalysisQuestion).where(AnalysisQuestion.set_id == aset.id))
    aset.parse_status = ParseStatus.pending
    aset.parse_error = None
    await db.commit()

    from app.tasks.file_tasks import parse_analysis_file_task
    task = parse_analysis_file_task.delay(aset.id)
    aset.task_id = task.id
    await db.commit()

    out = AnalysisSetOut.model_validate(aset)
    out.question_count = 0
    return out


@router.post("/{set_id}/analyze")
async def analyze(
    set_id: int,
    data: AnalyzeIn,
    teacher: Teacher = Depends(require_perm("analysis.edit")),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher, db, with_questions=True, edit=True)
    valid_ids = {q.id for q in aset.questions}
    ids = [i for i in data.question_ids if i in valid_ids]
    if not ids:
        raise HTTPException(status_code=400, detail="请至少勾选一道题目")

    need_ai: list[int] = []
    reused = 0
    id_set = set(ids)
    targets = [q for q in aset.questions if q.id in id_set]
    if data.force:
        need_ai = ids
    else:
        from app.services.question_bank_service import attach_bank_analysis
        await attach_bank_analysis(db, teacher.id, targets)
        for q in targets:
            if q.analysis_status == ParseStatus.done and q.analysis_content:
                reused += 1
                continue
            need_ai.append(q.id)

    for q in aset.questions:
        if q.id not in need_ai:
            continue
        q.selected = True
        q.analysis_status = ParseStatus.pending
        q.analysis_source = None
    await db.commit()

    if not need_ai:
        try:
            from app.tasks.knowledge_tasks import persist_analysis_kps_task
            persist_analysis_kps_task.delay(set_id)
        except Exception:
            pass
        return {"task_id": None, "count": 0, "reused": reused}

    from app.tasks.ai_tasks import analyze_questions_task
    task = analyze_questions_task.delay(set_id, need_ai, force=data.force)
    aset.task_id = task.id
    await db.commit()
    return {"task_id": task.id, "count": len(need_ai), "reused": reused}


@router.post("/{set_id}/save-to-bank")
async def save_to_bank(
    set_id: int,
    data: SaveToBankIn,
    teacher: Teacher = Depends(require_perm("analysis.edit")),
    db: AsyncSession = Depends(get_db),
):
    """将选中的题目复用入题库（questions 表）。重复题干不重复录入。"""
    aset = await _get_set_or_404(set_id, teacher, db, with_questions=True, edit=True)
    id_set = set(data.question_ids)
    items: list[dict] = []
    for q in aset.questions:
        if q.id not in id_set:
            continue
        explanation = None
        if q.analysis_content:
            from app.services.export_service import _analysis_lines
            explanation = "\n".join(_analysis_lines(q.analysis_content)) or None
        items.append({
            "content": q.content,
            "options": q.options,
            "answer": q.answer,
            "question_type": q.question_type,
            "difficulty": q.difficulty,
            "explanation": explanation,
            "analysis_content": q.analysis_content,
            "analysis_html": q.analysis_html,
            "tags": (q.analysis_content or {}).get("知识点") if q.analysis_content else None,
        })
    if not items:
        raise HTTPException(status_code=400, detail="没有可入库的题目")
    from app.services.question_bank_service import upsert_and_write_analysis, upsert_payloads
    _, created, skipped = await upsert_payloads(
        db,
        teacher_id=teacher.id,
        subject_id=aset.subject_id,
        grade_id=aset.grade_id,
        items=items,
    )
    for q in aset.questions:
        if q.id not in id_set or not q.analysis_content:
            continue
        await upsert_and_write_analysis(
            db,
            teacher_id=teacher.id,
            subject_id=aset.subject_id,
            grade_id=aset.grade_id,
            content=q.content,
            options=q.options,
            question_type=q.question_type,
            difficulty=q.difficulty,
            answer=q.answer,
            analysis_content=q.analysis_content,
            analysis_html=q.analysis_html,
            overwrite=True,
        )
    await db.commit()
    return {"count": created, "created": created, "skipped": skipped}


@router.get("/{set_id}/export")
async def export_set(
    set_id: int,
    format: str = "docx",
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher, db, with_questions=True)
    fmt = (format or "docx").lower()
    questions = [
        {
            "content": q.content,
            "options": q.options,
            "answer": q.answer,
            "selected": q.selected,
            "analysis_content": q.analysis_content,
        }
        for q in aset.questions
    ]
    from app.services.export_service import build_analysis_export
    try:
        data, media_type, ext = build_analysis_export(fmt, aset.name, questions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = quote(f"{aset.name}.{ext}")
    return StreamingResponse(
        io.BytesIO(data), media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.delete("/{set_id}", status_code=204)
async def delete_set(
    set_id: int,
    teacher: Teacher = Depends(require_perm("analysis.edit")),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher, db, delete=True)
    await db.delete(aset)
    await db.commit()
