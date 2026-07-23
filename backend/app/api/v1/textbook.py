from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.minio_client import upload_file, get_presigned_url, delete_file
from app.core.config import settings
from app.models.teacher import Teacher
from app.models.textbook import Textbook, TextbookChapter, TextbookImage, ParseStatus
from app.schemas.textbook import TextbookOut, ChapterOut, TextbookCreate
from app.api.deps import get_current_teacher
from pydantic import BaseModel
import uuid, os

router = APIRouter(prefix="/textbooks", tags=["课本管理"])

ALLOWED_TYPES = {"pdf", "doc", "docx", "txt", "epub", "mobi"}


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.get("", response_model=dict)
async def list_textbooks(
    subject_id: int | None = None,
    grade_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = select(Textbook).where(Textbook.teacher_id == teacher.id)
    if subject_id:
        q = q.where(Textbook.subject_id == subject_id)
    if grade_id:
        q = q.where(Textbook.grade_id == grade_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(Textbook.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [TextbookOut.model_validate(t) for t in items],
    }


@router.post("", response_model=TextbookOut, status_code=201)
async def upload_textbook(
    file: UploadFile = File(...),
    title: str = Form(...),
    subject_id: int = Form(...),
    grade_id: int = Form(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    ext = _ext(file.filename or "")
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式，支持：{', '.join(ALLOWED_TYPES)}")

    data = await file.read()
    object_name = f"{teacher.id}/{grade_id}/{subject_id}/{uuid.uuid4()}.{ext}"
    upload_file(settings.MINIO_BUCKET_TEXTBOOKS, object_name, data, file.content_type or "application/octet-stream")

    textbook = Textbook(
        teacher_id=teacher.id,
        subject_id=subject_id,
        grade_id=grade_id,
        title=title,
        file_name=file.filename,
        file_path=object_name,
        file_type=ext,
        file_size=len(data),
        parse_status=ParseStatus.pending,
    )
    db.add(textbook)
    await db.flush()
    await db.refresh(textbook)
    # 先提交，确保 worker 能查到该行（避免 dispatch-before-commit 竞态）
    await db.commit()

    # 触发异步解析任务
    from app.tasks.file_tasks import parse_textbook_task
    parse_textbook_task.delay(textbook.id)

    return textbook


@router.get("/{textbook_id}", response_model=TextbookOut)
async def get_textbook(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    tb = await _get_or_404(textbook_id, teacher.id, db)
    return tb


@router.get("/{textbook_id}/preview-url")
async def get_preview_url(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    tb = await _get_or_404(textbook_id, teacher.id, db)
    url = get_presigned_url(settings.MINIO_BUCKET_TEXTBOOKS, tb.file_path, expires_hours=2)
    return {"url": url, "file_type": tb.file_type}


@router.get("/{textbook_id}/chapters", response_model=list[ChapterOut])
async def get_chapters(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    await _get_or_404(textbook_id, teacher.id, db)
    result = await db.execute(
        select(TextbookChapter)
        .where(TextbookChapter.textbook_id == textbook_id, TextbookChapter.parent_id == None)
        .options(selectinload(TextbookChapter.children))
        .order_by(TextbookChapter.sort_order)
    )
    return result.scalars().all()


@router.post("/{textbook_id}/reparse", response_model=TextbookOut)
async def reparse_textbook(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """重新解析课本：清空旧章节，重置状态并重新触发解析任务"""
    tb = await _get_or_404(textbook_id, teacher.id, db)
    # 删除旧章节与旧图片
    await db.execute(
        delete(TextbookChapter).where(TextbookChapter.textbook_id == tb.id)
    )
    await db.execute(
        delete(TextbookImage).where(TextbookImage.textbook_id == tb.id)
    )
    tb.parse_status = ParseStatus.pending
    tb.parse_error = None
    await db.commit()

    from app.tasks.file_tasks import parse_textbook_task
    parse_textbook_task.delay(tb.id)

    await db.refresh(tb)
    return tb


@router.delete("/{textbook_id}", status_code=204)
async def delete_textbook(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    tb = await _get_or_404(textbook_id, teacher.id, db)
    delete_file(settings.MINIO_BUCKET_TEXTBOOKS, tb.file_path)
    await db.delete(tb)


@router.get("/{textbook_id}/images")
async def list_textbook_images(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """列出课本提取的插图（含临时访问 URL）"""
    await _get_or_404(textbook_id, teacher.id, db)
    result = await db.execute(
        select(TextbookImage)
        .where(TextbookImage.textbook_id == textbook_id)
        .order_by(TextbookImage.sort_order)
    )
    images = result.scalars().all()
    return [
        {
            "id": img.id,
            "page_number": img.page_number,
            "url": get_presigned_url(settings.MINIO_BUCKET_TEXTBOOKS, img.object_name, expires_hours=6),
        }
        for img in images
    ]


class ResolveImagesRequest(BaseModel):
    ids: list[int]


@router.post("/images/resolve")
async def resolve_image_urls(
    data: ResolveImagesRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """把课件引用的图片 id 批量解析为可访问 URL"""
    if not data.ids:
        return {}
    result = await db.execute(
        select(TextbookImage)
        .join(Textbook, Textbook.id == TextbookImage.textbook_id)
        .where(TextbookImage.id.in_(data.ids), Textbook.teacher_id == teacher.id)
    )
    images = result.scalars().all()
    return {
        str(img.id): get_presigned_url(
            settings.MINIO_BUCKET_TEXTBOOKS, img.object_name, expires_hours=6
        )
        for img in images
    }


async def _get_or_404(textbook_id: int, teacher_id: int, db: AsyncSession) -> Textbook:
    result = await db.execute(
        select(Textbook).where(Textbook.id == textbook_id, Textbook.teacher_id == teacher_id)
    )
    tb = result.scalar_one_or_none()
    if not tb:
        raise HTTPException(status_code=404, detail="课本不存在")
    return tb
