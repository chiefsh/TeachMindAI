from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func

from app.core.database import get_db
from app.core.minio_client import upload_file, get_presigned_url, delete_file, get_file_bytes
from app.core.config import settings
from app.models.teacher import Teacher
from app.models.textbook import Textbook, TextbookChapter, TextbookImage, ParseStatus
from app.models.courseware import Courseware
from app.models.homework import HomeworkPaper, HomeworkQuestion
from app.models.interaction import CoursewareSession, InteractionRecord
from app.schemas.textbook import TextbookOut, ChapterOut, TextbookCreate, TextbookRelatedCounts
from app.api.deps import get_current_teacher
from pydantic import BaseModel
import asyncio, base64, uuid, os

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
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件过大，最大支持 500MB")
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
    extra = None
    if tb.file_type == "pdf":
        extra = {
            "response-content-type": "application/pdf",
            "response-content-disposition": "inline",
        }
    url = get_presigned_url(
        settings.MINIO_BUCKET_TEXTBOOKS, tb.file_path, expires_hours=2, response_headers=extra,
    )
    return {"url": url, "file_type": tb.file_type}


@router.get("/{textbook_id}/chapters", response_model=list[ChapterOut])
async def get_chapters(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    await _get_or_404(textbook_id, teacher.id, db)
    rows = (
        await db.execute(
            select(TextbookChapter)
            .where(TextbookChapter.textbook_id == textbook_id)
            .order_by(TextbookChapter.sort_order, TextbookChapter.id)
        )
    ).scalars().all()

    # 一次查出全部章节，在内存拼树；不要走 relationship.children，
    # 异步会话里懒加载孙节点会 MissingGreenlet。
    by_parent: dict[int | None, list[TextbookChapter]] = {}
    for ch in rows:
        by_parent.setdefault(ch.parent_id, []).append(ch)

    def to_out(ch: TextbookChapter) -> ChapterOut:
        return ChapterOut(
            id=ch.id,
            title=ch.title,
            level=ch.level,
            sort_order=ch.sort_order,
            page_start=ch.page_start,
            page_end=ch.page_end,
            children=[to_out(c) for c in by_parent.get(ch.id, [])],
        )

    return [to_out(ch) for ch in by_parent.get(None, [])]


@router.post("/{textbook_id}/reparse", response_model=TextbookOut)
async def reparse_textbook(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """重新解析课本：清空旧章节，重置状态并重新触发解析任务"""
    tb = await _get_or_404(textbook_id, teacher.id, db)
    # 章节树自引用 parent_id，须先断开父子再删，否则 MySQL 1451
    await db.execute(
        update(TextbookChapter)
        .where(TextbookChapter.textbook_id == tb.id)
        .values(parent_id=None)
    )
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


@router.get("/{textbook_id}/related-counts", response_model=TextbookRelatedCounts)
async def get_related_counts(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """删除前提示：该书关联的课件、作业/试卷及其试题数量。"""
    await _get_or_404(textbook_id, teacher.id, db)
    return await _count_related(textbook_id, db)


@router.delete("/{textbook_id}", status_code=204)
async def delete_textbook(
    textbook_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    tb = await _get_or_404(textbook_id, teacher.id, db)
    await _purge_related(tb.id, db)
    # 章节树自引用 parent_id，须先断开再随课本删除
    await db.execute(
        update(TextbookChapter)
        .where(TextbookChapter.textbook_id == tb.id)
        .values(parent_id=None)
    )
    delete_file(settings.MINIO_BUCKET_TEXTBOOKS, tb.file_path)
    await db.delete(tb)


async def _courseware_ids(textbook_id: int, db: AsyncSession) -> list[int]:
    rows = (
        await db.execute(select(Courseware.id).where(Courseware.textbook_id == textbook_id))
    ).scalars().all()
    return list(rows)


async def _count_related(textbook_id: int, db: AsyncSession) -> TextbookRelatedCounts:
    cw_ids = await _courseware_ids(textbook_id, db)
    if not cw_ids:
        return TextbookRelatedCounts()
    hw = (
        await db.execute(
            select(func.count()).select_from(HomeworkPaper).where(
                HomeworkPaper.courseware_id.in_(cw_ids)
            )
        )
    ).scalar() or 0
    qs = (
        await db.execute(
            select(func.count()).select_from(HomeworkQuestion).join(
                HomeworkPaper, HomeworkPaper.id == HomeworkQuestion.paper_id
            ).where(HomeworkPaper.courseware_id.in_(cw_ids))
        )
    ).scalar() or 0
    return TextbookRelatedCounts(courseware=len(cw_ids), homework=hw, questions=qs)


async def _purge_related(textbook_id: int, db: AsyncSession) -> None:
    cw_ids = await _courseware_ids(textbook_id, db)
    if not cw_ids:
        return
    paper_ids = (
        await db.execute(
            select(HomeworkPaper.id).where(HomeworkPaper.courseware_id.in_(cw_ids))
        )
    ).scalars().all()
    if paper_ids:
        await db.execute(
            delete(HomeworkQuestion).where(HomeworkQuestion.paper_id.in_(list(paper_ids)))
        )
        await db.execute(
            delete(HomeworkPaper).where(HomeworkPaper.id.in_(list(paper_ids)))
        )
    session_ids = (
        await db.execute(
            select(CoursewareSession.id).where(CoursewareSession.courseware_id.in_(cw_ids))
        )
    ).scalars().all()
    if session_ids:
        await db.execute(
            delete(InteractionRecord).where(InteractionRecord.session_id.in_(list(session_ids)))
        )
        await db.execute(
            delete(CoursewareSession).where(CoursewareSession.id.in_(list(session_ids)))
        )
    await db.execute(delete(Courseware).where(Courseware.id.in_(cw_ids)))


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


# 内联图片的体积上限：base64 会膨胀约 1/3，过大的整页截图不值得塞进单个 HTML 文件
_INLINE_IMAGE_MAX_BYTES = 2 * 1024 * 1024
_INLINE_TOTAL_MAX_BYTES = 24 * 1024 * 1024


@router.post("/images/resolve-inline")
async def resolve_images_inline(
    data: ResolveImagesRequest,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """把图片 id 批量解析为 base64 data URI，供离线 HTML 内联。

    presigned URL 有时效，下载后的网页课件过期就丢图，所以离线场景改为内联。
    超出体积上限的图片不返回，调用方对这些图回退到 presigned URL。
    """
    if not data.ids:
        return {}

    result = await db.execute(
        select(TextbookImage)
        .join(Textbook, Textbook.id == TextbookImage.textbook_id)
        .where(TextbookImage.id.in_(data.ids), Textbook.teacher_id == teacher.id)
        .order_by(TextbookImage.sort_order, TextbookImage.id)
    )
    images = result.scalars().all()
    if not images:
        return {}

    async def _fetch(img: TextbookImage):
        try:
            raw = await asyncio.to_thread(
                get_file_bytes, settings.MINIO_BUCKET_TEXTBOOKS, img.object_name
            )
            return img, raw
        except Exception:
            return img, None

    out: dict[str, str] = {}
    total = 0
    for img, raw in await asyncio.gather(*[_fetch(i) for i in images]):
        if not raw or len(raw) > _INLINE_IMAGE_MAX_BYTES:
            continue
        if total + len(raw) > _INLINE_TOTAL_MAX_BYTES:
            break
        total += len(raw)
        encoded = base64.b64encode(raw).decode()
        out[str(img.id)] = f"data:{img.content_type or 'image/png'};base64,{encoded}"
    return out


async def _get_or_404(textbook_id: int, teacher_id: int, db: AsyncSession) -> Textbook:
    result = await db.execute(
        select(Textbook).where(Textbook.id == textbook_id, Textbook.teacher_id == teacher_id)
    )
    tb = result.scalar_one_or_none()
    if not tb:
        raise HTTPException(status_code=404, detail="课本不存在")
    return tb
