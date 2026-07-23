from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from urllib.parse import quote
import io

from app.core.database import get_db
from app.core.config import settings
from app.core.minio_client import get_file_bytes
from app.models.teacher import Teacher
from app.models.courseware import Courseware
from app.models.textbook import ParseStatus, TextbookImage, Textbook
from app.schemas.courseware import CoursewareCreate, CoursewareOut, CoursewareDetail
from app.api.deps import get_current_teacher
from app.services.export_service import build_export

router = APIRouter(prefix="/coursewares", tags=["课件管理"])


@router.get("", response_model=dict)
async def list_coursewares(
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = select(Courseware).where(Courseware.teacher_id == teacher.id).options(
        selectinload(Courseware.textbook)
    )
    # 课件本身不直接挂年级/科目，按其引用的课本进行过滤
    if grade_id or subject_id:
        q = q.join(Textbook, Textbook.id == Courseware.textbook_id)
        if grade_id:
            q = q.where(Textbook.grade_id == grade_id)
        if subject_id:
            q = q.where(Textbook.subject_id == subject_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.order_by(Courseware.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    items = []
    for cw in rows:
        o = CoursewareOut.model_validate(cw)
        if cw.textbook:
            o.grade_id = cw.textbook.grade_id
            o.subject_id = cw.textbook.subject_id
        items.append(o)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("", response_model=CoursewareOut, status_code=201)
async def create_courseware(
    data: CoursewareCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = Courseware(
        teacher_id=teacher.id,
        textbook_id=data.textbook_id,
        title=data.title,
        chapter_range=data.chapter_range,
        page_range=data.page_range,
        courseware_type=data.courseware_type,
        custom_prompt=data.custom_prompt,
        is_interactive=data.is_interactive,
        gen_status=ParseStatus.pending,
    )
    db.add(cw)
    await db.flush()
    await db.refresh(cw)
    # 先提交，确保 worker 能查到该行（避免 dispatch-before-commit 竞态）
    await db.commit()

    # 触发异步生成任务
    from app.tasks.ai_tasks import generate_courseware_task
    task = generate_courseware_task.delay(cw.id)
    cw.task_id = task.id
    await db.commit()

    return cw


@router.get("/{cw_id}", response_model=CoursewareDetail)
async def get_courseware(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher.id, db)
    return cw


@router.get("/{cw_id}/status")
async def get_courseware_status(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher.id, db)
    return {"id": cw.id, "gen_status": cw.gen_status, "task_id": cw.task_id}


@router.post("/{cw_id}/regenerate", response_model=CoursewareOut)
async def regenerate_courseware(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """重新生成课件：清空旧内容，重置状态并重新触发生成任务"""
    cw = await _get_or_404(cw_id, teacher.id, db)
    cw.content = None
    cw.gen_status = ParseStatus.pending
    await db.commit()

    from app.tasks.ai_tasks import generate_courseware_task
    task = generate_courseware_task.delay(cw.id)
    cw.task_id = task.id
    await db.commit()

    await db.refresh(cw)
    return cw


def _collect_image_ids(content: dict) -> list[int]:
    ids: list[int] = []
    for s in (content or {}).get("slides") or []:
        for iid in s.get("images") or []:
            if isinstance(iid, int):
                ids.append(iid)
            elif isinstance(iid, str) and iid.isdigit():
                ids.append(int(iid))
    return list(dict.fromkeys(ids))


@router.get("/{cw_id}/export")
async def export_courseware(
    cw_id: int,
    format: str = "pptx",
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """导出课件为 pptx / docx / pdf"""
    fmt = (format or "pptx").lower()
    if fmt not in ("pptx", "docx", "pdf"):
        raise HTTPException(status_code=400, detail="仅支持 pptx / docx / pdf")
    cw = await _get_or_404(cw_id, teacher.id, db)
    if not cw.content or cw.gen_status != ParseStatus.done:
        raise HTTPException(status_code=400, detail="课件尚未生成完成，无法导出")

    # 并行拉取引用图片，避免同步 MinIO 串行阻塞事件循环
    images: dict[int, bytes] = {}
    img_ids = _collect_image_ids(cw.content)
    if img_ids:
        import asyncio
        res = await db.execute(
            select(TextbookImage).where(TextbookImage.id.in_(img_ids))
        )
        img_rows = res.scalars().all()

        async def _fetch(img: TextbookImage):
            try:
                data = await asyncio.to_thread(
                    get_file_bytes, settings.MINIO_BUCKET_TEXTBOOKS, img.object_name
                )
                return img.id, data
            except Exception:
                return img.id, None

        for iid, data in await asyncio.gather(*[_fetch(img) for img in img_rows]):
            if data:
                images[iid] = data

    try:
        data, media_type, ext = build_export(fmt, cw.content, cw.title, images)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{e}")

    filename = quote(f"{cw.title}.{ext}")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.delete("/{cw_id}", status_code=204)
async def delete_courseware(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher.id, db)
    await db.delete(cw)


async def _get_or_404(cw_id: int, teacher_id: int, db: AsyncSession) -> Courseware:
    result = await db.execute(
        select(Courseware).where(Courseware.id == cw_id, Courseware.teacher_id == teacher_id)
    )
    cw = result.scalar_one_or_none()
    if not cw:
        raise HTTPException(status_code=404, detail="课件不存在")
    return cw
