from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.redis_client import get_redis
from app.core.config import settings
from app.models.teacher import Teacher
from app.schemas.auth import TeacherRegister, TeacherLogin, TokenResponse, TeacherProfile
from app.api.deps import get_current_teacher, bearer_scheme
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=TeacherProfile, status_code=201)
async def register(data: TeacherRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Teacher).where(Teacher.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    result = await db.execute(select(Teacher).where(Teacher.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    teacher = Teacher(
        username=data.username,
        email=data.email,
        real_name=data.real_name,
        hashed_password=get_password_hash(data.password),
    )
    db.add(teacher)
    await db.flush()
    await db.refresh(teacher)
    return teacher


@router.post("/login", response_model=TokenResponse)
async def login(data: TeacherLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Teacher).where(Teacher.username == data.username))
    teacher = result.scalar_one_or_none()
    if not teacher or not verify_password(data.password, teacher.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not teacher.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")

    token = create_access_token(
        {"sub": str(teacher.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        teacher_id=teacher.id,
        real_name=teacher.real_name,
        username=teacher.username,
    )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    redis=Depends(get_redis),
):
    token = credentials.credentials
    await redis.setex(f"blacklist:{token}", settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, "1")
    return {"message": "已退出登录"}


@router.get("/me", response_model=TeacherProfile)
async def get_me(teacher: Teacher = Depends(get_current_teacher)):
    return teacher
