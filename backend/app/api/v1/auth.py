from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.redis_client import get_redis
from app.core.config import settings
from app.models.teacher import Teacher
from app.schemas.auth import (
    TeacherRegister, TeacherLogin, TokenResponse, TeacherProfile,
    TeacherProfileUpdate, ChangePasswordIn, PublicAuthConfig,
)
from app.api.deps import get_current_teacher, bearer_scheme
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/config", response_model=PublicAuthConfig)
async def public_auth_config():
    """登录页用的公开配置，无需鉴权。"""
    return PublicAuthConfig(enable_regist=settings.ENABLE_REGIST)


@router.post("/register", response_model=TeacherProfile, status_code=201)
async def register(data: TeacherRegister, db: AsyncSession = Depends(get_db)):
    if not settings.ENABLE_REGIST:
        raise HTTPException(status_code=403, detail="当前未开放注册")
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


@router.patch("/me", response_model=TeacherProfile)
async def update_me(
    data: TeacherProfileUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    if data.real_name is not None:
        teacher.real_name = data.real_name
    if data.email is not None and data.email != teacher.email:
        exists = await db.execute(
            select(Teacher).where(Teacher.email == data.email, Teacher.id != teacher.id)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="邮箱已被注册")
        teacher.email = data.email
    await db.commit()
    await db.refresh(teacher)
    return teacher


@router.post("/change-password")
async def change_password(
    data: ChangePasswordIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.old_password, teacher.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    if data.old_password == data.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    teacher.hashed_password = get_password_hash(data.new_password)
    await db.commit()
    return {"message": "密码已更新"}
