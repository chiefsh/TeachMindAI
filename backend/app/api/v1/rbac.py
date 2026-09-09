from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.rbac import Role
from app.api.deps import require_perm, get_current_teacher
from app.schemas.rbac import (
    RoleOut, RoleCreate, RoleUpdate, PermissionOut,
    UserOut, UserCreate, UserUpdate, AssignmentOut, RoleBrief, ClassOptionOut,
    ColleagueOut, CollaboratorOut, CollaboratorIn, BatchCollaboratorIn,
)
from app.services import rbac_service as svc

router = APIRouter(tags=["用户角色"])


def _err(e: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


def _role_out(role: Role) -> RoleOut:
    codes = [p.permission_code for p in (role.permissions or [])]
    return RoleOut(
        id=role.id, code=role.code, name=role.name,
        is_system=role.is_system, is_super=role.is_super, permission_codes=codes,
    )


def _user_out(t: Teacher) -> UserOut:
    roles = []
    for ur in t.user_roles or []:
        if ur.role:
            roles.append(RoleBrief.model_validate(ur.role))
    assignments = []
    for a in getattr(t, "assignments", None) or []:
        assignments.append(AssignmentOut(
            id=a.id, grade_id=a.grade_id, subject_id=a.subject_id, class_id=a.class_id,
            grade_name=a.grade.name if a.grade else None,
            subject_name=a.subject.name if a.subject else None,
            class_name=a.school_class.name if a.school_class else None,
        ))
    return UserOut(
        id=t.id, username=t.username, email=t.email, real_name=t.real_name,
        is_active=t.is_active, is_super=bool(t.is_super), roles=roles, assignments=assignments,
    )


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(
    teacher: Teacher = Depends(require_perm("role.view", "role.manage", "user.view")),
    db: AsyncSession = Depends(get_db),
):
    return await svc.list_permissions(db)


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    teacher: Teacher = Depends(require_perm("role.view", "user.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await svc.list_roles(db, teacher)
    return [_role_out(r) for r in rows]


@router.post("/roles", response_model=RoleOut, status_code=201)
async def create_role(
    data: RoleCreate,
    teacher: Teacher = Depends(require_perm("role.manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        role = await svc.create_role(db, teacher, data.name, data.permission_codes)
    except ValueError as e:
        raise _err(e)
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.models.rbac import Role as RoleModel
    role = (await db.execute(
        select(RoleModel).options(selectinload(RoleModel.permissions)).where(RoleModel.id == role.id)
    )).scalar_one()
    return _role_out(role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    teacher: Teacher = Depends(require_perm("role.manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc.update_role(db, teacher, role_id, data.name, data.permission_codes)
    except ValueError as e:
        raise _err(e)
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.models.rbac import Role as RoleModel
    role = (await db.execute(
        select(RoleModel).options(selectinload(RoleModel.permissions)).where(RoleModel.id == role_id)
    )).scalar_one()
    return _role_out(role)


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: int,
    teacher: Teacher = Depends(require_perm("role.manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc.delete_role(db, teacher, role_id)
    except ValueError as e:
        raise _err(e)


@router.get("/users")
async def list_users(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    teacher: Teacher = Depends(require_perm("user.view")),
    db: AsyncSession = Depends(get_db),
):
    total, rows = await svc.list_users(db, teacher, keyword, page, page_size)
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [_user_out(t) for t in rows],
    }


@router.get("/users/class-options", response_model=list[ClassOptionOut])
async def class_options(
    teacher: Teacher = Depends(require_perm("user.view", "user.manage")),
    db: AsyncSession = Depends(get_db),
):
    rows = await svc.list_classes(db)
    return [ClassOptionOut(id=c.id, grade_id=c.grade_id, name=c.name) for c in rows]


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    teacher: Teacher = Depends(require_perm("user.view")),
    db: AsyncSession = Depends(get_db),
):
    try:
        t = await svc.get_user(db, teacher, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _user_out(t)


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    data: UserCreate,
    teacher: Teacher = Depends(require_perm("user.manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        t = await svc.create_user(db, teacher, data.model_dump())
    except ValueError as e:
        raise _err(e)
    return _user_out(t)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    data: UserUpdate,
    teacher: Teacher = Depends(require_perm("user.manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        t = await svc.update_user(db, teacher, user_id, data.model_dump(exclude_unset=True))
    except ValueError as e:
        raise _err(e)
    return _user_out(t)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    teacher: Teacher = Depends(require_perm("user.manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc.disable_user(db, teacher, user_id)
    except ValueError as e:
        raise _err(e)


@router.get("/colleagues", response_model=list[ColleagueOut])
async def list_colleagues(
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """全部启用用户，供协作者选择。"""
    from sqlalchemy import select
    q = select(Teacher).where(Teacher.is_active.is_(True), Teacher.id != teacher.id)
    rows = list((await db.execute(q.order_by(Teacher.id))).scalars().all())
    return [ColleagueOut(id=t.id, username=t.username, real_name=t.real_name) for t in rows]


_RESOURCE_MODELS = {
    "courseware": ("app.models.courseware", "Courseware"),
    "homework": ("app.models.homework", "HomeworkPaper"),
    "analysis": ("app.models.question_analysis", "AnalysisSet"),
    "grading": ("app.models.grading", "GradingAssignment"),
}


async def _load_resource(db, resource_type: str, resource_id: int):
    spec = _RESOURCE_MODELS.get(resource_type)
    if not spec:
        raise HTTPException(status_code=400, detail="不支持的资源类型")
    import importlib
    model = getattr(importlib.import_module(spec[0]), spec[1])
    return await db.get(model, resource_id)


@router.get("/resources/{resource_type}/{resource_id}/collaborators", response_model=list[CollaboratorOut])
async def list_collaborators(
    resource_type: str,
    resource_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.rbac import ResourceCollaborator
    from app.core.access import require_resource
    obj = await _load_resource(db, resource_type, resource_id)
    await require_resource(db, teacher, obj, resource_type, detail="资源不存在")
    rows = list((await db.execute(
        select(ResourceCollaborator).where(
            ResourceCollaborator.resource_type == resource_type,
            ResourceCollaborator.resource_id == resource_id,
        )
    )).scalars().all())
    names = {}
    if rows:
        ids = [r.teacher_id for r in rows]
        people = (await db.execute(select(Teacher).where(Teacher.id.in_(ids)))).scalars().all()
        names = {t.id: t for t in people}
    out = []
    for r in rows:
        t = names.get(r.teacher_id)
        out.append(CollaboratorOut(
            teacher_id=r.teacher_id,
            real_name=t.real_name if t else "",
            username=t.username if t else "",
            can_edit=bool(r.can_edit),
        ))
    return out


async def _apply_collaborators(
    db, teacher: Teacher, resource_type: str, resource_id: int,
    items: list[CollaboratorIn], *, replace: bool,
) -> bool:
    from sqlalchemy import select, delete
    from app.models.rbac import ResourceCollaborator
    from app.core.access import require_resource, can_manage_collab, peer_ids
    obj = await _load_resource(db, resource_type, resource_id)
    await require_resource(db, teacher, obj, resource_type, detail="资源不存在")
    if not await can_manage_collab(db, teacher, obj):
        return False
    owner = await db.get(Teacher, obj.teacher_id)
    allowed = set(await peer_ids(db, owner or teacher))
    existing = {}
    if replace:
        await db.execute(delete(ResourceCollaborator).where(
            ResourceCollaborator.resource_type == resource_type,
            ResourceCollaborator.resource_id == resource_id,
        ))
    else:
        rows = list((await db.execute(
            select(ResourceCollaborator).where(
                ResourceCollaborator.resource_type == resource_type,
                ResourceCollaborator.resource_id == resource_id,
            )
        )).scalars().all())
        existing = {r.teacher_id: r for r in rows}
    seen: set[int] = set()
    for it in items:
        if it.teacher_id == obj.teacher_id or it.teacher_id in seen:
            continue
        if it.teacher_id not in allowed:
            continue
        seen.add(it.teacher_id)
        row = existing.get(it.teacher_id)
        if row:
            row.can_edit = bool(it.can_edit)
        else:
            db.add(ResourceCollaborator(
                resource_type=resource_type, resource_id=resource_id,
                teacher_id=it.teacher_id, can_edit=bool(it.can_edit),
            ))
    return True


@router.put("/resources/{resource_type}/{resource_id}/collaborators", response_model=list[CollaboratorOut])
async def replace_collaborators(
    resource_type: str,
    resource_id: int,
    items: list[CollaboratorIn],
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    ok = await _apply_collaborators(db, teacher, resource_type, resource_id, items, replace=True)
    if not ok:
        raise HTTPException(status_code=403, detail="只有创建人或管理员可以配置协作者")
    await db.flush()
    return await list_collaborators(resource_type, resource_id, teacher, db)


@router.put("/resources/{resource_type}/collaborators/batch")
async def batch_collaborators(
    resource_type: str,
    data: BatchCollaboratorIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    updated = 0
    skipped = 0
    for rid in data.resource_ids:
        try:
            ok = await _apply_collaborators(
                db, teacher, resource_type, rid, data.items, replace=data.replace,
            )
        except HTTPException:
            ok = False
        if ok:
            updated += 1
        else:
            skipped += 1
    await db.flush()
    return {"updated": updated, "skipped": skipped}
