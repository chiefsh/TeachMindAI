from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.redis_client import get_redis
from app.models.teacher import Teacher

bearer_scheme = HTTPBearer()


async def get_current_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Teacher:
    token = credentials.credentials
    # 检查黑名单（登出的 token）
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
    return teacher
