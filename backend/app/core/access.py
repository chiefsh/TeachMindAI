"""资源可见范围与私有 ACL。角色权限在路由层；这里是数据范围。"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teacher import Teacher
from app.models.rbac import ResourceCollaborator

PRIVATE_TYPES = frozenset({"courseware", "homework", "analysis", "grading"})


def sees_all(teacher: Teacher) -> bool:
    if getattr(teacher, "is_super", False):
        return True
    if getattr(teacher, "is_admin", False):
        return True
    perms = getattr(teacher, "perm_codes", set()) or set()
    return "resource.view_all" in perms


# 兼容旧名
sees_all_in_org = sees_all


async def peer_ids(db: AsyncSession, teacher: Teacher) -> list[int]:
    """全部教师 id，供协作者选择与题库去重。"""
    rows = (await db.execute(select(Teacher.id))).scalars().all()
    return list(rows) or [teacher.id]


async def peer_ids_by_teacher_id(db: AsyncSession, teacher_id: int) -> list[int]:
    t = await db.get(Teacher, teacher_id)
    if not t:
        return [teacher_id]
    return await peer_ids(db, t)


async def org_member_ids(db: AsyncSession, teacher: Teacher) -> list[int] | None:
    """共享资产全站公共：None = 不按创建人过滤。"""
    return None


async def apply_org_scope(q, owner_col, db: AsyncSession, teacher: Teacher):
    return q


async def collab_ids(
    db: AsyncSession, teacher_id: int, resource_type: str, *, need_edit: bool = False,
) -> list[int]:
    q = select(ResourceCollaborator.resource_id).where(
        ResourceCollaborator.teacher_id == teacher_id,
        ResourceCollaborator.resource_type == resource_type,
    )
    if need_edit:
        q = q.where(ResourceCollaborator.can_edit.is_(True))
    return list((await db.execute(q)).scalars().all())


async def apply_private_scope(q, model, db: AsyncSession, teacher: Teacher, resource_type: str):
    if teacher.is_super or sees_all(teacher):
        return q
    extra = await collab_ids(db, teacher.id, resource_type)
    cond = model.teacher_id == teacher.id
    if extra:
        cond = or_(cond, model.id.in_(extra))
    return q.where(cond)


async def _collab_row(db: AsyncSession, resource_type: str, resource_id: int, teacher_id: int):
    return (await db.execute(
        select(ResourceCollaborator).where(
            ResourceCollaborator.resource_type == resource_type,
            ResourceCollaborator.resource_id == resource_id,
            ResourceCollaborator.teacher_id == teacher_id,
        )
    )).scalar_one_or_none()


async def can_view_resource(db: AsyncSession, teacher: Teacher, obj, resource_type: str) -> bool:
    owner_id = getattr(obj, "teacher_id", None)
    if owner_id is None:
        return False
    if teacher.is_super or sees_all(teacher):
        return True
    if owner_id == teacher.id:
        return True
    if resource_type in PRIVATE_TYPES:
        row = await _collab_row(db, resource_type, obj.id, teacher.id)
        return bool(row)
    return True  # 课本/题库等共享资产全站可见


async def can_edit_resource(db: AsyncSession, teacher: Teacher, obj, resource_type: str) -> bool:
    if not await can_view_resource(db, teacher, obj, resource_type):
        return False
    owner_id = obj.teacher_id
    if teacher.is_super or sees_all(teacher):
        return True
    if owner_id == teacher.id:
        return True
    if resource_type in PRIVATE_TYPES:
        row = await _collab_row(db, resource_type, obj.id, teacher.id)
        return bool(row and row.can_edit)
    return True  # 共享资产：有模块写权限即可改（路由层再拦）


async def can_delete_resource(db: AsyncSession, teacher: Teacher, obj) -> bool:
    owner_id = obj.teacher_id
    if teacher.is_super or sees_all(teacher):
        return True
    return owner_id == teacher.id


async def can_manage_collab(db: AsyncSession, teacher: Teacher, obj) -> bool:
    return await can_delete_resource(db, teacher, obj)


async def require_org_asset(db: AsyncSession, teacher: Teacher, obj, detail: str = "不存在"):
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


async def require_resource(
    db: AsyncSession, teacher: Teacher, obj, resource_type: str, *,
    edit: bool = False, delete: bool = False, detail: str = "不存在",
):
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    if not await can_view_resource(db, teacher, obj, resource_type):
        raise HTTPException(status_code=404, detail=detail)
    if delete and not await can_delete_resource(db, teacher, obj):
        raise HTTPException(status_code=403, detail="没有权限")
    if edit and not await can_edit_resource(db, teacher, obj, resource_type):
        raise HTTPException(status_code=403, detail="没有权限")
    return obj


async def teacher_names(db: AsyncSession, ids: list[int]) -> dict[int, str]:
    uniq = [i for i in dict.fromkeys(ids) if i]
    if not uniq:
        return {}
    rows = (await db.execute(select(Teacher.id, Teacher.real_name).where(Teacher.id.in_(uniq)))).all()
    return {i: n for i, n in rows}


async def stamp_access_many(
    db: AsyncSession, teacher: Teacher, objs: list, resource_type: str,
) -> list:
    if not objs:
        return objs
    names = await teacher_names(db, [o.teacher_id for o in objs])
    admin = sees_all(teacher)
    edit_set = set()
    if not admin:
        edit_set = set(await collab_ids(db, teacher.id, resource_type, need_edit=True))
    for o in objs:
        o.creator_name = names.get(o.teacher_id)
        o.is_owner = o.teacher_id == teacher.id
        o.can_edit = bool(admin or o.is_owner or o.id in edit_set)
        o.can_manage_collab = bool(admin or o.is_owner)
    return objs


async def stamp_org_assets(db: AsyncSession, objs: list) -> list:
    if not objs:
        return objs
    names = await teacher_names(db, [o.teacher_id for o in objs])
    for o in objs:
        o.creator_name = names.get(o.teacher_id)
    return objs
