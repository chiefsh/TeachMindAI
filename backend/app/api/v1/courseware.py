from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update
from sqlalchemy.orm import defer, selectinload
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional
from urllib.parse import quote, urlparse
from datetime import datetime
import asyncio
import copy
import io
import json

from app.core.database import get_db
from app.core.config import settings
from app.core.minio_client import get_file_bytes
from app.models.teacher import Teacher
from app.models.courseware import (
    Courseware, CoursewareVersion, RenderStyle, save_courseware_version,
    is_generation_stale, reap_stale_generation, courseware_progress_key,
)
from app.core.redis_client import get_redis
from app.models.homework import HomeworkPaper
from app.models.interaction import CoursewareSession, InteractionRecord
from app.models.textbook import ParseStatus, TextbookImage, Textbook
from app.schemas.courseware import (
    CoursewareCreate, CoursewareOut, CoursewareDetail, CoursewareUpdate, CoursewareCopyIn,
    SlidePatch, SlideInsert, SlideReorder, SlideOptimizeIn, CoursewareExportIn,
    CoursewareVersionOut, CoursewareVersionDetail,
)
from app.services.courseware_theme import PAGE_LABELS, page_kind
from app.api.deps import get_current_teacher, require_perm
from app.core.access import apply_private_scope, require_resource, stamp_access_many
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
    # 先只排 id，避免把整份 content JSON 带进 filesort（会撑爆 MySQL sort buffer）
    id_q = select(Courseware.id)
    id_q = await apply_private_scope(id_q, Courseware, db, teacher, "courseware")
    # 课件本身不直接挂年级/科目，按其引用的课本进行过滤
    if grade_id or subject_id:
        id_q = id_q.join(Textbook, Textbook.id == Courseware.textbook_id)
        if grade_id:
            id_q = id_q.where(Textbook.grade_id == grade_id)
        if subject_id:
            id_q = id_q.where(Textbook.subject_id == subject_id)

    total = (await db.execute(select(func.count()).select_from(id_q.subquery()))).scalar() or 0
    ids = (
        await db.execute(
            id_q.order_by(Courseware.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    if not ids:
        return {"total": total, "page": page, "page_size": page_size, "items": []}

    rows = (
        await db.execute(
            select(Courseware)
            .where(Courseware.id.in_(ids))
            .options(
                selectinload(Courseware.textbook),
                defer(Courseware.content),
                defer(Courseware.custom_prompt),
                defer(Courseware.chapter_range),
                defer(Courseware.page_range),
            )
        )
    ).scalars().all()
    stale_ids = [cw.id for cw in rows if is_generation_stale(cw)]
    if stale_ids:
        full = (
            await db.execute(
                select(Courseware)
                .where(Courseware.id.in_(stale_ids))
                .execution_options(populate_existing=True)
            )
        ).scalars().all()
        for cw in full:
            reap_stale_generation(cw)
        await db.commit()
    by_id = {cw.id: cw for cw in rows}
    rows = [by_id[i] for i in ids if i in by_id]
    await stamp_access_many(db, teacher, rows, "courseware")

    items = []
    for cw in rows:
        o = CoursewareOut.model_validate(cw)
        if cw.textbook:
            o.grade_id = cw.textbook.grade_id
            o.subject_id = cw.textbook.subject_id
        items.append(o)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/lab-experiments")
async def list_lab_experiments(
    teacher: Teacher = Depends(get_current_teacher),
):
    """互动动画目录（创建课件下拉的兜底数据源；前端优先走 GET /animations）。"""
    from app.services.animation_service import catalog_for_picker
    return catalog_for_picker()


@router.post("", response_model=CoursewareOut, status_code=201)
async def create_courseware(
    data: CoursewareCreate,
    teacher: Teacher = Depends(require_perm("courseware.create")),
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
        lesson_type=data.lesson_type.value,
        is_interactive=data.is_interactive,
        want_virtual_lab=bool(data.want_virtual_lab) and bool(data.is_interactive),
        virtual_lab_key=data.virtual_lab_key if data.is_interactive else None,
        animation_keys=(data.animation_keys if data.is_interactive else None),
        gen_status=ParseStatus.pending,
        gen_started_at=datetime.now(),
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
    cw = await _get_or_404(cw_id, teacher, db)
    await stamp_access_many(db, teacher, [cw], "courseware")
    return cw


@router.get("/{cw_id}/status")
async def get_courseware_status(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db)
    progress = None
    if cw.gen_status in (ParseStatus.pending, ParseStatus.processing):
        progress = await _read_progress(cw.id)
    return {
        "id": cw.id, "gen_status": cw.gen_status, "task_id": cw.task_id, "gen_error": cw.gen_error,
        "progress": progress,
    }


async def _read_progress(cw_id: int) -> dict | None:
    try:
        raw = await (await get_redis()).get(courseware_progress_key(cw_id))
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        return None


async def _clear_progress(cw_id: int) -> None:
    try:
        await (await get_redis()).delete(courseware_progress_key(cw_id))
    except Exception:  # noqa: BLE001
        pass


def _version_out(ver: CoursewareVersion, creator_name: str | None, *, with_content: bool = False):
    data = {
        "id": ver.id,
        "courseware_id": ver.courseware_id,
        "teacher_id": ver.teacher_id,
        "title": ver.title,
        "render_style": ver.render_style,
        "theme": ver.theme,
        "created_at": ver.created_at,
        "creator_name": creator_name,
    }
    if with_content:
        data["content"] = ver.content
        return CoursewareVersionDetail(**data)
    return CoursewareVersionOut(**data)


async def _get_version_or_404(cw: Courseware, vid: int, db: AsyncSession) -> CoursewareVersion:
    ver = (
        await db.execute(
            select(CoursewareVersion).where(
                CoursewareVersion.id == vid,
                CoursewareVersion.courseware_id == cw.id,
            )
        )
    ).scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="历史版本不存在")
    return ver


@router.get("/{cw_id}/versions", response_model=list[CoursewareVersionOut])
async def list_courseware_versions(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db)

    async def _fetch():
        return (
            await db.execute(
                select(CoursewareVersion, Teacher.real_name)
                .outerjoin(Teacher, Teacher.id == CoursewareVersion.teacher_id)
                .where(CoursewareVersion.courseware_id == cw.id)
                .order_by(CoursewareVersion.id.desc())
            )
        ).all()

    rows = await _fetch()
    # 升级前已生成的课件补一版当前内容，避免历史列表空白
    if not rows and isinstance(cw.content, dict):
        await save_courseware_version(db, cw, cw.teacher_id, skip_if_same=False)
        await db.commit()
        rows = await _fetch()
    return [_version_out(ver, name) for ver, name in rows]


@router.get("/{cw_id}/versions/{vid}", response_model=CoursewareVersionDetail)
async def get_courseware_version(
    cw_id: int,
    vid: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db)
    ver = await _get_version_or_404(cw, vid, db)
    name = (
        await db.execute(select(Teacher.real_name).where(Teacher.id == ver.teacher_id))
    ).scalar_one_or_none()
    return _version_out(ver, name, with_content=True)


@router.delete("/{cw_id}/versions/{vid}", status_code=204)
async def delete_courseware_version(
    cw_id: int,
    vid: int,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    ver = await _get_version_or_404(cw, vid, db)
    await db.delete(ver)
    await db.commit()


@router.post("/{cw_id}/versions/{vid}/apply", response_model=CoursewareDetail)
async def apply_courseware_version(
    cw_id: int,
    vid: int,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    """把历史版本覆盖为当前课件；覆盖前先把当前内容存成一版。"""
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    if cw.gen_status in (ParseStatus.pending, ParseStatus.processing):
        raise HTTPException(status_code=400, detail="正在生成中，请稍后再试")
    ver = await _get_version_or_404(cw, vid, db)
    if not isinstance(ver.content, dict):
        raise HTTPException(status_code=400, detail="该版本没有内容")
    await save_courseware_version(db, cw, teacher.id)
    cw.title = ver.title
    cw.content = copy.deepcopy(ver.content)
    flag_modified(cw, "content")
    try:
        cw.render_style = RenderStyle(ver.render_style)
    except ValueError:
        pass
    if ver.theme:
        cw.theme = ver.theme
    cw.gen_status = ParseStatus.done
    cw.gen_error = None
    await db.commit()
    await db.refresh(cw)
    await stamp_access_many(db, teacher, [cw], "courseware")
    return cw


@router.post("/{cw_id}/regenerate", response_model=CoursewareOut)
async def regenerate_courseware(
    cw_id: int,
    data: CoursewareCreate,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    """按新配置重新生成。旧内容保留到新内容生成成功为止，失败则继续用旧内容。"""
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    if cw.gen_status in (ParseStatus.pending, ParseStatus.processing):
        raise HTTPException(status_code=400, detail="正在生成中，请稍后再试")
    await save_courseware_version(db, cw, teacher.id)
    cw.title = data.title
    cw.textbook_id = data.textbook_id
    cw.chapter_range = data.chapter_range
    cw.page_range = data.page_range
    cw.courseware_type = data.courseware_type
    cw.render_style = data.render_style
    cw.theme = data.theme
    cw.custom_prompt = data.custom_prompt
    cw.lesson_type = data.lesson_type.value
    cw.is_interactive = data.is_interactive
    cw.want_virtual_lab = bool(data.want_virtual_lab) and bool(data.is_interactive)
    cw.virtual_lab_key = data.virtual_lab_key if data.is_interactive else None
    cw.animation_keys = data.animation_keys if data.is_interactive else None
    flag_modified(cw, "animation_keys")
    flag_modified(cw, "chapter_range")
    flag_modified(cw, "page_range")
    cw.gen_status = ParseStatus.pending
    cw.gen_error = None
    cw.gen_started_at = datetime.now()
    cw.task_id = None
    await db.commit()
    await _clear_progress(cw.id)

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
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    old = cw.title
    cw.title = data.title
    if cw.content and old != data.title:
        cw.content = _apply_title(cw.content, old, data.title)
        flag_modified(cw, "content")
    await db.commit()
    await db.refresh(cw)
    return cw


@router.get("/{cw_id}/copy-title")
async def suggest_copy_title(
    cw_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    src = await _get_or_404(cw_id, teacher, db)
    return {"title": await _next_copy_title(src.title, teacher.id, db)}


@router.post("/{cw_id}/copy", response_model=CoursewareOut, status_code=201)
async def copy_courseware(
    cw_id: int,
    data: CoursewareCopyIn = CoursewareCopyIn(),
    teacher: Teacher = Depends(require_perm("courseware.create")),
    db: AsyncSession = Depends(get_db),
):
    src = await _get_or_404(cw_id, teacher, db)
    title = data.title or await _next_copy_title(src.title, teacher.id, db)
    content = _apply_title(src.content, src.title, title) if src.content else None
    gen_status = src.gen_status
    gen_error = src.gen_error
    if gen_status in (ParseStatus.pending, ParseStatus.processing):
        # 副本不带生成任务，只能复制源课件当前已有的内容
        gen_status = ParseStatus.done if content else ParseStatus.failed
        gen_error = None if content else "复制时源课件尚未生成完成，请重新生成"
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
        lesson_type=src.lesson_type,
        content=content,
        gen_status=gen_status,
        gen_error=gen_error,
        is_interactive=src.is_interactive,
        want_virtual_lab=bool(src.want_virtual_lab),
        virtual_lab_key=src.virtual_lab_key,
        animation_keys=copy.deepcopy(src.animation_keys) if src.animation_keys else None,
        task_id=None,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


# ─── 按页编辑 ─────────────────────────────────────────────────────────

_EDITABLE = (
    "type", "title", "subtitle", "bullets", "answers", "pairs", "content", "more", "notes",
    "prompt", "solution", "left_title", "right_title",
)


def _ensure_slides(cw: Courseware) -> list:
    if not isinstance(cw.content, dict):
        cw.content = {"meta": {"title": cw.title}, "slides": []}
    slides = cw.content.get("slides")
    if not isinstance(slides, list):
        cw.content["slides"] = []
        slides = cw.content["slides"]
    return slides


def _reindex(slides: list) -> None:
    for i, s in enumerate(slides):
        if isinstance(s, dict):
            s["index"] = i + 1


def _get_slide(cw: Courseware, index: int) -> dict:
    slides = _ensure_slides(cw)
    if index < 0 or index >= len(slides) or not isinstance(slides[index], dict):
        raise HTTPException(status_code=404, detail="页面不存在")
    return slides[index]


def _blank_slide(kind: str) -> dict:
    k = page_kind(kind)
    return {
        "index": 1,
        "type": k,
        "title": PAGE_LABELS.get(k, "新页面"),
        "subtitle": "",
        "bullets": [],
        "content": "",
        "notes": "",
    }


def _require_editable(cw: Courseware) -> None:
    if cw.gen_status != ParseStatus.done or not cw.content:
        raise HTTPException(status_code=400, detail="课件尚未生成完成，无法编辑页面")


def _any_slide_optimizing(slides: list) -> bool:
    return any(isinstance(s, dict) and s.get("edit_status") == "processing" for s in slides)


async def _has_open_session(cw_id: int, db: AsyncSession) -> bool:
    n = (
        await db.execute(
            select(func.count()).select_from(CoursewareSession).where(
                CoursewareSession.courseware_id == cw_id,
                CoursewareSession.is_open == True,  # noqa: E712
            )
        )
    ).scalar() or 0
    return n > 0


async def _require_structure_ok(cw: Courseware, db: AsyncSession) -> None:
    if await _has_open_session(cw.id, db):
        raise HTTPException(status_code=409, detail="有进行中的课堂互动，无法增删或重排页面")
    if _any_slide_optimizing(_ensure_slides(cw)):
        raise HTTPException(status_code=409, detail="有页面正在 AI 优化，请稍后再改结构")


@router.put("/{cw_id}/slides/reorder")
async def reorder_slides(
    cw_id: int,
    data: SlideReorder,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    _require_editable(cw)
    await _require_structure_ok(cw, db)
    slides = _ensure_slides(cw)
    n = len(slides)
    if sorted(data.order) != list(range(n)):
        raise HTTPException(status_code=400, detail="排序必须覆盖全部页面且不重复")
    cw.content["slides"] = [slides[i] for i in data.order]
    _reindex(cw.content["slides"])
    flag_modified(cw, "content")
    await db.commit()
    return {"count": n}


@router.post("/{cw_id}/slides")
async def insert_slide(
    cw_id: int,
    data: SlideInsert,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    _require_editable(cw)
    await _require_structure_ok(cw, db)
    slides = _ensure_slides(cw)
    at = len(slides) if data.index is None else data.index
    at = max(0, min(at, len(slides)))
    slide = _blank_slide(data.type)
    slides.insert(at, slide)
    _reindex(slides)
    flag_modified(cw, "content")
    await db.commit()
    return {"index": at, "slide": slide}


@router.get("/{cw_id}/slides/{index}")
async def get_slide(
    cw_id: int,
    index: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    slide = _get_slide(cw, index)
    return {
        "index": index,
        "edit_status": slide.get("edit_status") or "idle",
        "task_id": slide.get("task_id"),
        "slide": slide,
    }


@router.patch("/{cw_id}/slides/{index}")
async def patch_slide(
    cw_id: int,
    index: int,
    data: SlidePatch,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    _require_editable(cw)
    slide = _get_slide(cw, index)
    if slide.get("edit_status") == "processing":
        raise HTTPException(status_code=409, detail="本页正在 AI 优化，请稍后再保存")
    payload = data.model_dump(exclude_unset=True)
    if "type" in payload and payload["type"]:
        payload["type"] = page_kind(payload["type"])
    for k, v in payload.items():
        if k in _EDITABLE:
            slide[k] = v
    if "pairs" in payload and payload["pairs"] is not None:
        # 导出（Word/PPT）仍按 columns 两栏画，保存配对时同步
        pairs = payload["pairs"]
        slide["columns"] = [
            {"title": slide.get("left_title") or "常见误区", "items": [p["wrong"] for p in pairs]},
            {"title": slide.get("right_title") or "正确说法", "items": [p["right"] for p in pairs]},
        ]
    flag_modified(cw, "content")
    await db.commit()
    return {"index": index, "slide": slide}


@router.delete("/{cw_id}/slides/{index}", status_code=204)
async def delete_slide(
    cw_id: int,
    index: int,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    _require_editable(cw)
    await _require_structure_ok(cw, db)
    slides = _ensure_slides(cw)
    if index < 0 or index >= len(slides):
        raise HTTPException(status_code=404, detail="页面不存在")
    if len(slides) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一页")
    slides.pop(index)
    _reindex(slides)
    flag_modified(cw, "content")
    await db.commit()


@router.post("/{cw_id}/slides/{index}/optimize")
async def optimize_slide(
    cw_id: int,
    index: int,
    data: SlideOptimizeIn,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, edit=True)
    _require_editable(cw)
    slide = _get_slide(cw, index)
    if slide.get("edit_status") == "processing":
        raise HTTPException(status_code=409, detail="本页正在优化，请稍候")
    slide["edit_status"] = "processing"
    slide["edit_error"] = None
    flag_modified(cw, "content")
    await db.commit()

    from app.tasks.ai_tasks import optimize_courseware_slide_task
    task = optimize_courseware_slide_task.delay(cw.id, index, data.instruction, data.mode)
    slide["task_id"] = task.id
    flag_modified(cw, "content")
    await db.commit()
    return {"index": index, "task_id": task.id, "edit_status": "processing"}


def _collect_image_ids(content: dict) -> list[int]:
    ids: list[int] = []
    for s in (content or {}).get("slides") or []:
        for iid in s.get("images") or []:
            if isinstance(iid, int):
                ids.append(iid)
            elif isinstance(iid, str) and iid.isdigit():
                ids.append(int(iid))
    return list(dict.fromkeys(ids))


async def _courseware_play_url(cw: Courseware, request: Request, db: AsyncSession) -> str:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        ref = request.headers.get("referer") or ""
        parsed = urlparse(ref)
        if parsed.scheme and parsed.netloc:
            origin = f"{parsed.scheme}://{parsed.netloc}"
    if not origin:
        return ""
    token = (
        await db.execute(
            select(CoursewareSession.token).where(
                CoursewareSession.courseware_id == cw.id,
                CoursewareSession.is_open == True,  # noqa: E712
            ).order_by(CoursewareSession.id.desc()).limit(1)
        )
    ).scalar()
    if token:
        return f"{origin}/s/{token}"
    return f"{origin}/courseware/{cw.id}"


def _decode_shots(raw: dict[str, str] | None) -> dict[int, bytes]:
    import base64
    out: dict[int, bytes] = {}
    for key, val in (raw or {}).items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(val, str) or len(val) > 6_000_000:
            continue
        payload = val.split(",", 1)[-1] if val.startswith("data:") else val
        try:
            data = base64.b64decode(payload, validate=False)
        except Exception:
            continue
        if 80 < len(data) < 4_000_000:
            out[idx] = data
    return out


async def _export_courseware(
    cw_id: int, fmt: str, request: Request, teacher: Teacher, db: AsyncSession,
    shots: dict[int, bytes] | None = None,
) -> StreamingResponse:
    if fmt not in ("pptx", "docx", "pdf"):
        raise HTTPException(status_code=400, detail="仅支持 pptx / docx / pdf")
    cw = await _get_or_404(cw_id, teacher, db)
    if not cw.content or cw.gen_status != ParseStatus.done:
        raise HTTPException(status_code=400, detail="课件尚未生成完成，无法导出")

    images: dict[int, bytes] = {}
    img_ids = _collect_image_ids(cw.content)
    if img_ids:
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

    play_url = await _courseware_play_url(cw, request, db) if fmt == "pptx" else ""
    try:
        data, media_type, ext = await asyncio.to_thread(
            build_export, fmt, cw.content, cw.title, images, cw.theme, play_url, shots,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{e}")

    filename = quote(f"{cw.title}.{ext}")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/{cw_id}/export")
async def export_courseware(
    request: Request,
    cw_id: int,
    format: str = "pptx",
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """导出课件为 pptx / docx / pdf"""
    return await _export_courseware(cw_id, (format or "pptx").lower(), request, teacher, db)


@router.post("/{cw_id}/export")
async def export_courseware_with_shots(
    request: Request,
    cw_id: int,
    body: CoursewareExportIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """导出课件；PPT 可附带互动页截图。"""
    fmt = (body.format or "pptx").lower()
    shots = _decode_shots(body.shots) if fmt == "pptx" else None
    return await _export_courseware(cw_id, fmt, request, teacher, db, shots)


@router.delete("/{cw_id}", status_code=204)
async def delete_courseware(
    cw_id: int,
    teacher: Teacher = Depends(require_perm("courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    cw = await _get_or_404(cw_id, teacher, db, delete=True)
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


async def _get_or_404(
    cw_id: int, teacher: Teacher, db: AsyncSession, *, edit: bool = False, delete: bool = False,
) -> Courseware:
    result = await db.execute(select(Courseware).where(Courseware.id == cw_id))
    cw = result.scalar_one_or_none()
    cw = await require_resource(
        db, teacher, cw, "courseware", edit=edit, delete=delete, detail="课件不存在",
    )
    if reap_stale_generation(cw):
        await db.commit()
    return cw
