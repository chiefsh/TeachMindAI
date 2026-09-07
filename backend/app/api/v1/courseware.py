from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional
from urllib.parse import quote
import copy
import io

from app.core.database import get_db
from app.core.config import settings
from app.core.minio_client import get_file_bytes
from app.models.teacher import Teacher
from app.models.courseware import Courseware
from app.models.homework import HomeworkPaper
from app.models.interaction import CoursewareSession, InteractionRecord
from app.models.textbook import ParseStatus, TextbookImage, Textbook
from app.schemas.courseware import CoursewareCreate, CoursewareOut, CoursewareDetail, CoursewareUpdate
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
        render_style=data.render_style,
        theme=data.theme,
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


def _apply_title(content: dict | None, old: str, new: str) -> dict | None:
    """同步课件 JSON 里的封面/meta 标题。"""
    if not content:
        return content
    data = copy.deepcopy(content)
    meta = data.get("meta")
    if isinstance(meta, dict) and (not meta.get("title") or meta.get("title") == old):
        meta["title"] = new
    for s in data.get("slides") or []:
        if not isinstance(s, dict):
            continue
        if s.get("type") in ("title", "cover") and (not s.get("title") or s.get("title") == old):
            s["title"] = new
    return data


async def _next_copy_title(base: str, teacher_id: int, db: AsyncSession) -> str:
    """在同一教师下为 base 生成「base_副本N」，N 取已有最大序号 + 1。"""
    prefix = f"{base}_副本"
    rows = (
        await db.execute(
            select(Courseware.title).where(Courseware.teacher_id == teacher_id)
        )
    ).scalars().all()
    max_n = 0
    for t in rows:
        rest = (t or "")[len(prefix):]
        if (t or "").startswith(prefix) and rest.isdigit():
            max_n = max(max_n, int(rest))
    n = max_n + 1
    suffix = f"_副本{n}"
    stem = base[: max(1, 256 - len(suffix))]
    return f"{stem}{suffix}"


@router.patch("/{cw_id}", response_model=CoursewareOut)
async def update_courseware(
    cw_id: int,
    data: CoursewareUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher.id, db)
    old = cw.title
    cw.title = data.title
    if cw.content and old != data.title:
        cw.content = _apply_title(cw.content, old, data.title)
        flag_modified(cw, "content")
    await db.commit()
    await db.refresh(cw)
    return cw


@router.post("/{cw_id}/copy", response_model=CoursewareOut, status_code=201)
async def copy_courseware(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    src = await _get_or_404(cw_id, teacher.id, db)
    title = await _next_copy_title(src.title, teacher.id, db)
    content = _apply_title(src.content, src.title, title) if src.content else None
    gen_status = src.gen_status
    if gen_status == ParseStatus.processing:
        gen_status = ParseStatus.done if content else ParseStatus.pending
    clone = Courseware(
        teacher_id=teacher.id,
        textbook_id=src.textbook_id,
        title=title,
        chapter_range=copy.deepcopy(src.chapter_range) if src.chapter_range else None,
        page_range=copy.deepcopy(src.page_range) if src.page_range else None,
        courseware_type=src.courseware_type,
        render_style=src.render_style,
        theme=src.theme,
        custom_prompt=src.custom_prompt,
        content=content,
        gen_status=gen_status,
        is_interactive=src.is_interactive,
        task_id=None,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


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
        data, media_type, ext = build_export(fmt, cw.content, cw.title, images, cw.theme)
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
    session_ids = (
        await db.execute(
            select(CoursewareSession.id).where(CoursewareSession.courseware_id == cw_id)
        )
    ).scalars().all()
    if session_ids:
        ids = list(session_ids)
        await db.execute(delete(InteractionRecord).where(InteractionRecord.session_id.in_(ids)))
        await db.execute(delete(CoursewareSession).where(CoursewareSession.id.in_(ids)))
    # 作业可独立存在，只解除对课件的引用，避免外键拦住删除
    await db.execute(
        update(HomeworkPaper)
        .where(HomeworkPaper.courseware_id == cw_id)
        .values(courseware_id=None)
    )
    await db.delete(cw)


async def _get_or_404(cw_id: int, teacher_id: int, db: AsyncSession) -> Courseware:
    result = await db.execute(
        select(Courseware).where(Courseware.id == cw_id, Courseware.teacher_id == teacher_id)
    )
    cw = result.scalar_one_or_none()
    if not cw:
        raise HTTPException(status_code=404, detail="课件不存在")
    return cw
