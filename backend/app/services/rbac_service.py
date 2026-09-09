"""角色 / 用户：权限解析、种子与 CRUD。"""
from __future__ import annotations

import secrets
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import (
    PERMISSION_CATALOG, ALL_PERM_CODES, SYSTEM_ROLES, implies_view,
)
from app.core.security import get_password_hash
from app.models.rbac import (
    Permission, Role, RolePermission, UserRole, TeacherAssignment,
)
from app.models.teacher import Teacher
from app.models.education import Grade, Subject
from app.models.student import SchoolClass


def has_perm(teacher: Teacher, *codes: str) -> bool:
    if getattr(teacher, "is_super", False):
        return True
    perms: set[str] = getattr(teacher, "perm_codes", set()) or set()
    for code in codes:
        if code in perms:
            return True
        view = implies_view(code)
        # 不把 view 当成 manage；只允许「有 manage 则能 view」在调用 view 时处理
        if code.endswith(".view"):
            stem = code[:-5]
            if f"{stem}.manage" in perms or f"{stem}.edit" in perms or f"{stem}.create" in perms:
                return True
        _ = view
    return False


def is_admin(teacher: Teacher) -> bool:
    return bool(getattr(teacher, "is_super", False) or getattr(teacher, "is_admin", False))


is_org_admin = is_admin


async def load_rbac(db: AsyncSession, teacher: Teacher) -> Teacher:
    """给当前请求的 Teacher 挂上 perm_codes / 角色摘要，不另开会话。"""
    user_role_ids = list((await db.execute(
        select(UserRole.role_id).where(UserRole.teacher_id == teacher.id)
    )).scalars().all())
    roles: list[Role] = []
    if user_role_ids:
        roles = list((await db.execute(select(Role).where(Role.id.in_(user_role_ids)))).scalars().all())
    codes: set[str] = set()
    if teacher.is_super:
        codes = set(ALL_PERM_CODES)
    elif user_role_ids:
        codes = set((await db.execute(
            select(RolePermission.permission_code).where(RolePermission.role_id.in_(user_role_ids))
        )).scalars().all())
    teacher.perm_codes = codes
    teacher.rbac_roles = roles
    teacher.is_admin = teacher.is_super or any(r.code == "admin" and r.is_system for r in roles)
    teacher.is_org_admin = teacher.is_admin
    rows = list((await db.execute(
        select(TeacherAssignment)
        .options(
            selectinload(TeacherAssignment.grade),
            selectinload(TeacherAssignment.subject),
            selectinload(TeacherAssignment.school_class),
        )
        .where(TeacherAssignment.teacher_id == teacher.id)
        .order_by(TeacherAssignment.id)
    )).scalars().all())
    teacher.work_assignments = rows
    return teacher


def profile_dict(teacher: Teacher) -> dict:
    roles = getattr(teacher, "rbac_roles", []) or []
    assigns = []
    for a in getattr(teacher, "work_assignments", []) or []:
        assigns.append({
            "grade_id": a.grade_id,
            "subject_id": a.subject_id,
            "class_id": a.class_id,
            "grade_name": a.grade.name if getattr(a, "grade", None) else None,
            "subject_name": a.subject.name if getattr(a, "subject", None) else None,
            "class_name": a.school_class.name if getattr(a, "school_class", None) else None,
        })
    return {
        "id": teacher.id,
        "username": teacher.username,
        "email": teacher.email,
        "real_name": teacher.real_name,
        "avatar": teacher.avatar,
        "is_active": teacher.is_active,
        "is_super": bool(teacher.is_super),
        "roles": [{"id": r.id, "code": r.code, "name": r.name, "is_system": r.is_system} for r in roles],
        "permissions": sorted(getattr(teacher, "perm_codes", set()) or []),
        "assignments": assigns,
    }


async def seed_rbac(db: AsyncSession, settings) -> None:
    # 权限目录
    existing = {p.code: p for p in (await db.execute(select(Permission))).scalars().all()}
    for i, (code, module, name) in enumerate(PERMISSION_CATALOG):
        row = existing.get(code)
        if row:
            row.module = module
            row.name = name
            row.sort_order = i
        else:
            db.add(Permission(code=code, module=module, name=name, sort_order=i))
    await db.flush()
    obsolete = [p for p in existing.values() if p.code not in ALL_PERM_CODES]
    if obsolete:
        codes = [p.code for p in obsolete]
        await db.execute(delete(RolePermission).where(RolePermission.permission_code.in_(codes)))
        await db.execute(delete(Permission).where(Permission.code.in_(codes)))
        await db.flush()

    # 系统角色 + 权限对齐
    sys_roles = (await db.execute(select(Role).where(Role.is_system.is_(True)))).scalars().all()
    by_code = {r.code: r for r in sys_roles}
    for spec in SYSTEM_ROLES:
        role = by_code.get(spec["code"])
        if not role:
            role = Role(
                org_id=None,
                code=spec["code"],
                name=spec["name"],
                is_system=True,
                is_super=spec["is_super"],
            )
            db.add(role)
            await db.flush()
            by_code[spec["code"]] = role
        else:
            role.name = spec["name"]
            role.is_super = spec["is_super"]
        await db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        db.add_all([
            RolePermission(role_id=role.id, permission_code=code)
            for code in sorted(spec["perms"])
        ])
    await db.flush()

    # 超管只建一次
    super_user = (await db.execute(
        select(Teacher).where(Teacher.is_super.is_(True))
    )).scalar_one_or_none()
    username = (getattr(settings, "SUPER_ADMIN_USERNAME", None) or "").strip()
    password = getattr(settings, "SUPER_ADMIN_PASSWORD", None) or ""
    if super_user is None and username and password:
        taken = (await db.execute(select(Teacher).where(Teacher.username == username))).scalar_one_or_none()
        if taken:
            if not taken.is_super:
                # 用户名被占用且不是超管：不抢号，留给运维改环境变量
                pass
        else:
            email = (getattr(settings, "SUPER_ADMIN_EMAIL", None) or f"{username}@local").strip()
            real_name = (getattr(settings, "SUPER_ADMIN_REAL_NAME", None) or "超级管理员").strip()
            dup_email = (await db.execute(select(Teacher).where(Teacher.email == email))).scalar_one_or_none()
            if dup_email:
                email = f"{username}@super.local"
            super_user = Teacher(
                username=username,
                email=email,
                real_name=real_name or "超级管理员",
                hashed_password=get_password_hash(password),
                is_super=True,
                is_active=True,
            )
            db.add(super_user)
            await db.flush()
            db.add(UserRole(teacher_id=super_user.id, role_id=by_code["super_admin"].id))

    if super_user:
        has_sr = (await db.execute(
            select(UserRole).where(
                UserRole.teacher_id == super_user.id,
                UserRole.role_id == by_code["super_admin"].id,
            )
        )).scalar_one_or_none()
        if not has_sr:
            db.add(UserRole(teacher_id=super_user.id, role_id=by_code["super_admin"].id))

    # 无角色的旧账号挂默认制作者
    creator_id = by_code["creator"].id
    all_users = list((await db.execute(
        select(Teacher).where(Teacher.is_super.is_(False))
    )).scalars().all())
    for t in all_users:
        has_role = (await db.execute(
            select(UserRole.id).where(UserRole.teacher_id == t.id).limit(1)
        )).scalars().first()
        if has_role is None:
            db.add(UserRole(teacher_id=t.id, role_id=creator_id))

    await db.commit()


def _assert_assignable_roles(roles: list[Role]) -> None:
    for r in roles:
        if r.is_super or r.code == "super_admin":
            raise ValueError("不能分配超级管理员角色")


async def list_permissions(db: AsyncSession) -> list[Permission]:
    return list((await db.execute(select(Permission).order_by(Permission.sort_order))).scalars().all())


async def list_roles(db: AsyncSession, actor: Teacher) -> list[Role]:
    q = select(Role).options(selectinload(Role.permissions)).order_by(Role.is_system.desc(), Role.id)
    if not actor.is_super:
        q = q.where(Role.is_super.is_(False))
    rows = list((await db.execute(q)).scalars().all())
    if not actor.is_super:
        rows = [r for r in rows if r.code != "super_admin"]
    return rows


async def create_role(
    db: AsyncSession, actor: Teacher, name: str, permission_codes: list[str],
) -> Role:
    name = name.strip()
    if not name:
        raise ValueError("角色名称不能为空")
    codes = _valid_codes(permission_codes)
    role = Role(org_id=None, code=f"tmp_{secrets.token_hex(4)}", name=name[:64], is_system=False, is_super=False)
    db.add(role)
    await db.flush()
    role.code = f"custom_{role.id}"
    db.add_all([RolePermission(role_id=role.id, permission_code=c) for c in codes])
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(
    db: AsyncSession, actor: Teacher, role_id: int, name: str | None, permission_codes: list[str] | None,
) -> Role:
    role = await db.get(Role, role_id)
    if not role:
        raise ValueError("角色不存在")
    if role.is_super or role.code == "super_admin":
        raise ValueError("不能修改超级管理员角色")
    if role.is_system:
        raise ValueError("系统角色权限由程序维护，不能修改")
    if name is not None:
        t = name.strip()
        if not t:
            raise ValueError("角色名称不能为空")
        role.name = t[:64]
    if permission_codes is not None:
        await db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        db.add_all([
            RolePermission(role_id=role.id, permission_code=c) for c in _valid_codes(permission_codes)
        ])
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, actor: Teacher, role_id: int) -> None:
    role = await db.get(Role, role_id)
    if not role:
        raise ValueError("角色不存在")
    if role.is_system:
        raise ValueError("不能删除系统角色")
    n = (await db.execute(select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id))).scalar() or 0
    if n:
        raise ValueError("仍有用户使用该角色")
    await db.delete(role)
    await db.commit()


def _valid_codes(codes: list[str]) -> list[str]:
    return sorted({c for c in codes if c in ALL_PERM_CODES})


async def list_users(
    db: AsyncSession, actor: Teacher, keyword: str | None, page: int, page_size: int,
) -> tuple[int, list[Teacher]]:
    filters = []
    if keyword:
        like = f"%{keyword.strip()}%"
        filters.append(
            Teacher.username.like(like) | Teacher.real_name.like(like) | Teacher.email.like(like)
        )
    count_q = select(func.count()).select_from(Teacher)
    q = select(Teacher)
    if filters:
        count_q = count_q.where(*filters)
        q = q.where(*filters)
    total = (await db.execute(count_q)).scalar() or 0
    rows = list((await db.execute(
        q.options(
            selectinload(Teacher.user_roles).selectinload(UserRole.role),
            selectinload(Teacher.assignments).selectinload(TeacherAssignment.grade),
            selectinload(Teacher.assignments).selectinload(TeacherAssignment.subject),
            selectinload(Teacher.assignments).selectinload(TeacherAssignment.school_class),
        )
        .order_by(Teacher.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all())
    return total, rows


async def get_user(db: AsyncSession, actor: Teacher, user_id: int) -> Teacher:
    t = (await db.execute(
        select(Teacher)
        .options(
            selectinload(Teacher.user_roles).selectinload(UserRole.role),
            selectinload(Teacher.assignments).selectinload(TeacherAssignment.grade),
            selectinload(Teacher.assignments).selectinload(TeacherAssignment.subject),
            selectinload(Teacher.assignments).selectinload(TeacherAssignment.school_class),
        )
        .where(Teacher.id == user_id)
    )).scalar_one_or_none()
    if not t:
        raise ValueError("用户不存在")
    return t


async def create_user(db: AsyncSession, actor: Teacher, data: dict) -> Teacher:
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    real_name = (data.get("real_name") or "").strip()
    password = data.get("password") or ""
    if not username or not email or not real_name or len(password) < 6:
        raise ValueError("请填写用户名、姓名、邮箱，密码至少 6 位")
    if (await db.execute(select(Teacher).where(Teacher.username == username))).scalar_one_or_none():
        raise ValueError("用户名已存在")
    if (await db.execute(select(Teacher).where(Teacher.email == email))).scalar_one_or_none():
        raise ValueError("邮箱已被注册")
    t = Teacher(
        username=username,
        email=email,
        real_name=real_name[:64],
        hashed_password=get_password_hash(password),
        is_super=False,
        is_active=True,
    )
    db.add(t)
    await db.flush()
    role_ids = data.get("role_ids") or []
    await _set_user_roles(db, actor, t, role_ids)
    await _set_assignments(db, t.id, data.get("assignments") or [])
    await db.commit()
    return await get_user(db, actor, t.id)


async def update_user(db: AsyncSession, actor: Teacher, user_id: int, data: dict) -> Teacher:
    t = await get_user(db, actor, user_id)
    if t.is_super:
        if not actor.is_super:
            raise ValueError("不能修改超级管理员")
        if data.get("is_active") is False:
            raise ValueError("不能禁用超级管理员")
        if "role_ids" in data:
            raise ValueError("不能修改超级管理员的角色")
    if data.get("real_name") is not None:
        name = str(data["real_name"]).strip()
        if not name:
            raise ValueError("姓名不能为空")
        t.real_name = name[:64]
    if data.get("email") is not None:
        email = str(data["email"]).strip()
        dup = (await db.execute(
            select(Teacher).where(Teacher.email == email, Teacher.id != t.id)
        )).scalar_one_or_none()
        if dup:
            raise ValueError("邮箱已被注册")
        t.email = email
    if data.get("is_active") is not None and not t.is_super:
        t.is_active = bool(data["is_active"])
    if data.get("password"):
        if len(data["password"]) < 6:
            raise ValueError("密码至少 6 位")
        t.hashed_password = get_password_hash(data["password"])
    if "role_ids" in data and not t.is_super:
        await _set_user_roles(db, actor, t, data["role_ids"] or [])
    if "assignments" in data:
        await _set_assignments(db, t.id, data["assignments"] or [])
    await db.commit()
    return await get_user(db, actor, t.id)


async def disable_user(db: AsyncSession, actor: Teacher, user_id: int) -> None:
    t = await get_user(db, actor, user_id)
    if t.is_super:
        raise ValueError("不能删除超级管理员")
    if t.id == actor.id:
        raise ValueError("不能删除自己")
    t.is_active = False
    await db.commit()


async def _set_user_roles(db: AsyncSession, actor: Teacher, t: Teacher, role_ids: list[int]) -> None:
    roles = []
    if role_ids:
        roles = list((await db.execute(select(Role).where(Role.id.in_(role_ids)))).scalars().all())
        if len(roles) != len(set(role_ids)):
            raise ValueError("角色不存在")
        _assert_assignable_roles(roles)
    await db.execute(delete(UserRole).where(UserRole.teacher_id == t.id))
    if roles:
        db.add_all([UserRole(teacher_id=t.id, role_id=r.id) for r in roles])


async def _set_assignments(db: AsyncSession, teacher_id: int, rows: list[dict]) -> None:
    await db.execute(delete(TeacherAssignment).where(TeacherAssignment.teacher_id == teacher_id))
    seen: set[tuple] = set()
    for row in rows:
        grade_id = row.get("grade_id")
        subject_id = row.get("subject_id")
        class_id = row.get("class_id") or None
        if not grade_id or not subject_id:
            continue
        key = (grade_id, class_id, subject_id)
        if key in seen:
            continue
        seen.add(key)
        if not await db.get(Grade, grade_id) or not await db.get(Subject, subject_id):
            raise ValueError("年级或科目不存在")
        if class_id and not await db.get(SchoolClass, class_id):
            raise ValueError("班级不存在")
        db.add(TeacherAssignment(
            teacher_id=teacher_id, grade_id=grade_id, class_id=class_id, subject_id=subject_id,
        ))
    from app.models.education import TeacherSubject
    await db.execute(delete(TeacherSubject).where(TeacherSubject.teacher_id == teacher_id))
    seen_gs: set[tuple] = set()
    for grade_id, class_id, subject_id in seen:
        gs = (grade_id, subject_id)
        if gs in seen_gs:
            continue
        seen_gs.add(gs)
        db.add(TeacherSubject(teacher_id=teacher_id, grade_id=grade_id, subject_id=subject_id))


async def list_classes(db: AsyncSession) -> list[SchoolClass]:
    """开户绑定时列出全部行政班。"""
    return list((await db.execute(
        select(SchoolClass).order_by(SchoolClass.grade_id, SchoolClass.name)
    )).scalars().all())
