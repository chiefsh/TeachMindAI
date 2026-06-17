import app.core.proxy  # noqa: F401  # 必须最先导入：清理 socks 代理，避免 litellm 崩溃
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.core.redis_client import close_redis
from app.core.minio_client import init_buckets
from app.core.seed import seed_education_data, seed_subject_prompts
from app.api.v1 import auth, education, textbook, question, courseware, homework, student, settings, ws, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（生产环境应使用 Alembic）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 注入基础数据（学段/年级/科目）
    try:
        await seed_education_data()
    except Exception:
        pass
    # 注入各科目默认课件提示词
    try:
        await seed_subject_prompts()
    except Exception:
        pass
    # 初始化 MinIO Bucket
    try:
        init_buckets()
    except Exception:
        pass
    yield
    await close_redis()


app = FastAPI(
    title="AI 教育平台",
    description="AI 辅助教师日常教学工作平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/v1")
app.include_router(education.router, prefix="/api/v1")
app.include_router(textbook.router, prefix="/api/v1")
app.include_router(question.router, prefix="/api/v1")
app.include_router(courseware.router, prefix="/api/v1")
app.include_router(homework.router, prefix="/api/v1")
app.include_router(student.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(ws.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AI教育平台"}
