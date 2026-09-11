from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_teacher, require_perm
from app.models.teacher import Teacher
from app.models.animation import InteractiveAsset
from app.schemas.animation import AnimationOut, AnimationCreate, AnimationUpdate
from app.services import animation_service as svc
from app.services.rbac_service import is_admin

router = APIRouter(prefix="/animations", tags=["互动动画"])


def _can_edit(teacher: Teacher, row: InteractiveAsset) -> bool:
    if is_admin(teacher):
        return True
    return row.origin == "teacher" and row.teacher_id == teacher.id


def _can_view(teacher: Teacher, row: InteractiveAsset) -> bool:
    if row.origin == "system" or is_admin(teacher):
        return True
    return row.teacher_id == teacher.id


@router.get("", response_model=dict)
async def list_animations(
    subject: str | None = Query(None),
    teacher: Teacher = Depends(require_perm("animation.view", "courseware.view")),
    db: AsyncSession = Depends(get_db),
):
    view_all = is_admin(teacher)
    rows = await svc.list_assets(db, teacher.id, subject=subject, view_all=view_all)
    return {"items": [svc.to_out(r) for r in rows]}


@router.get("/{anim_id}", response_model=AnimationOut)
async def get_animation(
    anim_id: int,
    teacher: Teacher = Depends(require_perm("animation.view", "courseware.view")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(InteractiveAsset, anim_id)
    if not row or not _can_view(teacher, row):
        raise HTTPException(status_code=404, detail="动画不存在")
    return svc.to_out(row)


@router.get("/{anim_id}/html", response_class=HTMLResponse)
async def get_animation_html(
    anim_id: int,
    teacher: Teacher = Depends(require_perm("animation.view", "courseware.view")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(InteractiveAsset, anim_id)
    if not row or not _can_view(teacher, row):
        raise HTTPException(status_code=404, detail="动画不存在")
    html = await svc.html_for_row(db, row)
    if not html:
        raise HTTPException(status_code=500, detail="动画尚未生成")
    return HTMLResponse(html)


@router.post("", response_model=AnimationOut, status_code=201)
async def create_animation(
    data: AnimationCreate,
    teacher: Teacher = Depends(require_perm("animation.edit", "courseware.create")),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.duplicate_from_template(
            db, teacher.id, data.template_key, data.title,
            data.keywords, data.knowledge_tags,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return svc.to_out(row)


@router.patch("/{anim_id}", response_model=AnimationOut)
async def update_animation(
    anim_id: int,
    data: AnimationUpdate,
    teacher: Teacher = Depends(require_perm("animation.edit", "courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(InteractiveAsset, anim_id)
    if not row:
        raise HTTPException(status_code=404, detail="动画不存在")
    if not _can_edit(teacher, row):
        raise HTTPException(status_code=403, detail="不能改系统预置动画，请先另存")
    if data.title is not None:
        row.title = data.title
    if data.keywords is not None:
        row.keywords = data.keywords
    if data.knowledge_tags is not None:
        row.knowledge_tags = data.knowledge_tags
    await db.commit()
    await db.refresh(row)
    return svc.to_out(row)


@router.post("/{anim_id}/render", response_model=AnimationOut)
async def rerender_animation(
    anim_id: int,
    teacher: Teacher = Depends(require_perm("animation.edit", "courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(InteractiveAsset, anim_id)
    if not row:
        raise HTTPException(status_code=404, detail="动画不存在")
    if not _can_edit(teacher, row) and row.origin != "system":
        raise HTTPException(status_code=403, detail="无权重新渲染")
    html = await svc.render_and_store(db, row)
    if not html:
        raise HTTPException(status_code=500, detail="渲染失败")
    return svc.to_out(row)


@router.delete("/{anim_id}")
async def delete_animation(
    anim_id: int,
    teacher: Teacher = Depends(require_perm("animation.edit", "courseware.edit")),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(InteractiveAsset, anim_id)
    if not row:
        raise HTTPException(status_code=404, detail="动画不存在")
    if row.origin == "system":
        raise HTTPException(status_code=400, detail="系统预置动画不能删除")
    if not _can_edit(teacher, row):
        raise HTTPException(status_code=403, detail="无权删除")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
