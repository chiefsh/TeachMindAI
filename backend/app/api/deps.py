from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.redis_client import get_redis
from app.models.teacher import Teacher
from app.services.rbac_service import load_rbac, has_perm

bearer_scheme = HTTPBearer()


async def get_current_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Teacher:
    token = credentials.credentials
    if await redis.get(f"blacklist:{token}"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已失效")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    teacher_id = payload.get("sub")
    if not teacher_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")

    result = await db.execute(select(Teacher).where(Teacher.id == int(teacher_id)))
    teacher = result.scalar_one_or_none()
    if not teacher or not teacher.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    await load_rbac(db, teacher)
    return teacher


def require_perm(*codes: str):
    """需要 codes 中任一权限；超管放行。"""
    async def _dep(teacher: Teacher = Depends(get_current_teacher)) -> Teacher:
        if not has_perm(teacher, *codes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限")
        return teacher
    return _dep


def require_super():
    async def _dep(teacher: Teacher = Depends(get_current_teacher)) -> Teacher:
        if not teacher.is_super:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅超级管理员可操作")
        return teacher
    return _dep
