from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.minio_client import upload_file, delete_file
from app.core.config import settings
from app.models.teacher import Teacher
from app.models.question import Question, QuestionType, DifficultyLevel, QuestionImport, coerce_tags
from app.models.textbook import ParseStatus
from app.schemas.question import QuestionOut, QuestionCreate, QuestionFilter, QuestionImportOut, QuestionBatchDeleteIn
from app.api.deps import get_current_teacher
from app.services.question_media import (
    public_images, verify_asset_sig, is_safe_object_name,
    read_question_asset, guess_content_type,
)
from pydantic import BaseModel
import re
import uuid


def _to_out(q: Question) -> QuestionOut:
    out = QuestionOut.model_validate(q)
    out.images = public_images(q.images, q.teacher_id)
    return out

router = APIRouter(prefix="/questions", tags=["题库管理"])

ALLOWED_TYPES = {"pdf", "doc", "docx", "txt", "epub", "mobi", "jpg", "jpeg", "png", "webp"}


def _to_question_type(val) -> QuestionType:
    try:
        return QuestionType(val)
    except Exception:
        return QuestionType.short_answer


def _to_difficulty(val) -> DifficultyLevel:
    try:
        return DifficultyLevel(val)
    except Exception:
        return DifficultyLevel.medium


def _fallback_split(text: str) -> list[dict]:
    """无 LLM 时的兜底：按题号或空行拆分，统一作为简答题。"""
    parts = re.split(r"\n(?=\s*\d+\s*[.、．)])", text)
    items: list[dict] = []
    for p in parts:
        c = p.strip()
        if len(c) >= 4:
            items.append({"content": c})
    if not items and text.strip():
        items = [{"content": text.strip()}]
    return items


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.get("", response_model=dict)
async def list_questions(
    subject_id: Optional[int] = None,
    grade_id: Optional[int] = None,
    question_type: Optional[QuestionType] = None,
    difficulty: Optional[DifficultyLevel] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = select(Question).where(Question.teacher_id == teacher.id)
    if subject_id:
        q = q.where(Question.subject_id == subject_id)
    if grade_id:
        q = q.where(Question.grade_id == grade_id)
    if question_type:
        q = q.where(Question.question_type == question_type)
    if difficulty:
        q = q.where(Question.difficulty == difficulty)
    if keyword:
        q = q.where(Question.content.ilike(f"%{keyword}%"))

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar()

    q = q.order_by(Question.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    items = result.scalars().all()

    return {"total": total, "page": page, "page_size": page_size, "items": [_to_out(i) for i in items]}


@router.post("", response_model=QuestionOut, status_code=201)
async def create_question(
    data: QuestionCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = Question(teacher_id=teacher.id, **data.model_dump())
    db.add(q)
    await db.flush()
    await db.refresh(q)
    return _to_out(q)


class ManualQuestionsIn(BaseModel):
    text: str
    subject_id: int
    grade_id: int
    use_ai: bool = True


@router.post("/manual", status_code=201)
async def create_questions_manual(
    data: ManualQuestionsIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """手动录入：可一次录入一道或多道题。use_ai=True 时用大模型自动拆分识别题型/选项/答案。"""
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请输入题目内容")

    parsed: list[dict] = []
    if data.use_ai:
        from app.services.ai_service import _get_default_llm, parse_questions_from_text
        cfg = await _get_default_llm(teacher.id, db)
        if cfg:
            try:
                parsed = await parse_questions_from_text(cfg, text)
            except Exception:
                parsed = []
    if not parsed:
        parsed = _fallback_split(text)

    created: list[Question] = []
    for item in parsed:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        q = Question(
            teacher_id=teacher.id,
            subject_id=data.subject_id,
            grade_id=data.grade_id,
            question_type=_to_question_type(item.get("question_type")),
            difficulty=_to_difficulty(item.get("difficulty")),
            content=content[:4000],
            options=item.get("options") or None,
            images=item.get("images") or None,
            answer=(item.get("answer") or None),
            explanation=(item.get("explanation") or None),
            tags=coerce_tags(item.get("tags") or item.get("知识点")),
        )
        db.add(q)
        created.append(q)

    if not created:
        raise HTTPException(status_code=400, detail="未能识别出有效题目，请检查输入")

    await db.flush()
    for q in created:
        await db.refresh(q)
    return {"count": len(created), "items": [_to_out(q) for q in created]}


@router.post("/import-file", status_code=202)
async def import_question_file(
    file: UploadFile = File(...),
    subject_id: int = Form(...),
    grade_id: int = Form(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    ext = _ext(file.filename or "")
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式，支持：{', '.join(ALLOWED_TYPES)}")

    data = await file.read()
    object_name = f"{teacher.id}/{subject_id}/{uuid.uuid4()}.{ext}"
    upload_file(settings.MINIO_BUCKET_QUESTIONS, object_name, data, file.content_type or "application/octet-stream")

    rec = QuestionImport(
        teacher_id=teacher.id,
        subject_id=subject_id,
        grade_id=grade_id,
        file_name=(file.filename or object_name)[:256],
        file_type=ext,
        source_file_path=object_name,
        parse_status=ParseStatus.pending.value,
    )
    db.add(rec)
    await db.flush()

    from app.tasks.file_tasks import parse_question_file_task
    task = parse_question_file_task.delay(
        teacher_id=teacher.id,
        subject_id=subject_id,
        grade_id=grade_id,
        bucket=settings.MINIO_BUCKET_QUESTIONS,
        object_name=object_name,
        file_type=ext,
        import_id=rec.id,
    )
    rec.task_id = task.id
    await db.commit()
    return {"task_id": task.id, "import_id": rec.id, "message": "文件已上传，正在后台解析"}


@router.get("/imports")
async def list_question_imports(
    page: int = 1,
    page_size: int = 20,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    base = select(QuestionImport).where(QuestionImport.teacher_id == teacher.id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(QuestionImport.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [QuestionImportOut.model_validate(r) for r in rows],
    }


@router.post("/batch-delete")
async def batch_delete_questions(
    data: QuestionBatchDeleteIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    ids = list({int(i) for i in (data.ids or []) if i})
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要删除的题目")
    result = await db.execute(
        select(Question).where(Question.teacher_id == teacher.id, Question.id.in_(ids))
    )
    rows = result.scalars().all()
    for q in rows:
        await db.delete(q)
    return {"count": len(rows)}


@router.get("/assets/{object_name:path}")
async def get_question_asset(
    object_name: str,
    exp: int = Query(...),
    sig: str = Query(...),
):
    """题干/选项配图。用列表接口下发的签名 URL 访问，不走 Bearer。"""
    try:
        teacher_id = int(object_name.split("/", 1)[0])
    except (TypeError, ValueError, IndexError):
        raise HTTPException(status_code=404, detail="图片不存在")
    if not verify_asset_sig(object_name, teacher_id, exp, sig):
        raise HTTPException(status_code=403, detail="图片链接无效或已过期")
    if not is_safe_object_name(object_name, teacher_id):
        raise HTTPException(status_code=404, detail="图片不存在")
    try:
        data = read_question_asset(object_name)
    except Exception:
        raise HTTPException(status_code=404, detail="图片不存在")
    return Response(content=data, media_type=guess_content_type(object_name))


@router.delete("/{question_id}", status_code=204)
async def delete_question(
    question_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Question).where(Question.id == question_id, Question.teacher_id == teacher.id)
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    await db.delete(q)
