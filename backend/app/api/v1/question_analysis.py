"""试题分析：导入试题 → 拆题 → 勾选 → AI 图解解析 → 查看/入库/导出。"""
import io
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from urllib.parse import quote

from app.core.database import get_db
from app.core.config import settings
from app.core.minio_client import upload_file
from app.models.teacher import Teacher
from app.models.education import Grade, Subject
from app.models.question import Question
from app.models.textbook import ParseStatus
from app.models.question_analysis import AnalysisSet, AnalysisQuestion
from app.schemas.question_analysis import (
    AnalysisSetOut, AnalysisSetDetail, AnalysisQuestionOut,
    ManualImportIn, AnalyzeIn, SaveToBankIn,
)
from app.api.deps import get_current_teacher

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


async def _get_set_or_404(set_id: int, teacher_id: int, db: AsyncSession, with_questions: bool = False) -> AnalysisSet:
    q = select(AnalysisSet).where(AnalysisSet.id == set_id, AnalysisSet.teacher_id == teacher_id)
    if with_questions:
        q = q.options(selectinload(AnalysisSet.questions))
    aset = (await db.execute(q)).scalar_one_or_none()
    if not aset:
        raise HTTPException(status_code=404, detail="试题批次不存在")
    return aset


@router.get("", response_model=list[AnalysisSetOut])
async def list_sets(
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(AnalysisSet, func.count(AnalysisQuestion.id))
        .outerjoin(AnalysisQuestion, AnalysisQuestion.set_id == AnalysisSet.id)
        .where(AnalysisSet.teacher_id == teacher.id)
    )
    if grade_id:
        q = q.where(AnalysisSet.grade_id == grade_id)
    if subject_id:
        q = q.where(AnalysisSet.subject_id == subject_id)
    q = q.group_by(AnalysisSet.id).order_by(AnalysisSet.created_at.desc())
    rows = (await db.execute(q)).all()
    out: list[AnalysisSetOut] = []
    for aset, cnt in rows:
        item = AnalysisSetOut.model_validate(aset)
        item.question_count = cnt or 0
        out.append(item)
    return out


@router.post("/import-manual", response_model=AnalysisSetDetail, status_code=201)
async def import_manual(
    data: ManualImportIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """富文本/纯文本录入：默认调用 LLM 拆题（失败回退按题号拆分）。"""
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请输入试题内容")

    from app.services.ai_service import _get_default_llm, parse_questions_from_text
    from app.services.file_service import _fallback_split_dicts, _coerce_qtype, _coerce_difficulty

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
    for item in parsed:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        seq += 1
        db.add(AnalysisQuestion(
            set_id=aset.id, teacher_id=teacher.id, seq=seq,
            content=content[:8000], options=item.get("options") or None,
            answer=(item.get("answer") or None),
            question_type=_coerce_qtype(item.get("question_type")),
            difficulty=_coerce_difficulty(item.get("difficulty")),
        ))
    if seq == 0:
        raise HTTPException(status_code=400, detail="未能识别出有效题目，请检查输入")

    await db.commit()
    aset = await _get_set_or_404(aset.id, teacher.id, db, with_questions=True)
    detail = AnalysisSetDetail.model_validate(aset)
    detail.question_count = len(aset.questions)
    return detail


@router.post("/import-file", response_model=AnalysisSetOut, status_code=201)
async def import_file(
    file: UploadFile = File(...),
    grade_id: int = Form(...),
    subject_id: int = Form(...),
    name: Optional[str] = Form(None),
    teacher: Teacher = Depends(get_current_teacher),
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
    aset = await _get_set_or_404(set_id, teacher.id, db, with_questions=True)
    detail = AnalysisSetDetail.model_validate(aset)
    detail.question_count = len(aset.questions)
    return detail


@router.get("/{set_id}/status")
async def get_status(
    set_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher.id, db, with_questions=True)
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


@router.post("/{set_id}/analyze")
async def analyze(
    set_id: int,
    data: AnalyzeIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher.id, db, with_questions=True)
    valid_ids = {q.id for q in aset.questions}
    ids = [i for i in data.question_ids if i in valid_ids]
    if not ids:
        raise HTTPException(status_code=400, detail="请至少勾选一道题目")

    # 置为待解析并 commit，保证 worker 能读到
    for q in aset.questions:
        if q.id in ids:
            q.selected = True
            q.analysis_status = ParseStatus.pending
    await db.commit()

    from app.tasks.ai_tasks import analyze_questions_task
    task = analyze_questions_task.delay(set_id, ids)
    aset.task_id = task.id
    await db.commit()
    return {"task_id": task.id, "count": len(ids)}


@router.post("/{set_id}/save-to-bank")
async def save_to_bank(
    set_id: int,
    data: SaveToBankIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """将选中的题目复用入题库（questions 表）。"""
    aset = await _get_set_or_404(set_id, teacher.id, db, with_questions=True)
    id_set = set(data.question_ids)
    count = 0
    for q in aset.questions:
        if q.id not in id_set:
            continue
        explanation = None
        if q.analysis_content:
            from app.services.export_service import _analysis_lines
            explanation = "\n".join(_analysis_lines(q.analysis_content)) or None
        db.add(Question(
            teacher_id=teacher.id,
            subject_id=aset.subject_id,
            grade_id=aset.grade_id,
            question_type=q.question_type,
            difficulty=q.difficulty,
            content=q.content[:4000],
            options=q.options or None,
            answer=q.answer or None,
            explanation=explanation,
        ))
        count += 1
    if count == 0:
        raise HTTPException(status_code=400, detail="没有可入库的题目")
    await db.commit()
    return {"count": count}


@router.get("/{set_id}/export")
async def export_set(
    set_id: int,
    format: str = "docx",
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher.id, db, with_questions=True)
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
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    aset = await _get_set_or_404(set_id, teacher.id, db)
    await db.delete(aset)
    await db.commit()
