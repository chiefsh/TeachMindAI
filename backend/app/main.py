import app.core.proxy  # noqa: F401  # 必须最先导入：清理 socks 代理，避免 litellm 崩溃
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.database import engine, Base
from app.core.redis_client import close_redis
from app.core.minio_client import init_buckets
from app.core.seed import seed_education_data, seed_subject_prompts
from app.api.v1 import auth, education, textbook, question, courseware, homework, student, settings, ws, dashboard, interaction, question_analysis, knowledge


# create_all 不会给已有表补索引，启动时幂等补齐热查询字段
_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_students_teacher_id ON students (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_students_teacher_grade ON students (teacher_id, grade_id)",
    "CREATE INDEX IF NOT EXISTS ix_exam_results_teacher_id ON exam_results (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_exam_results_teacher_subject_exam ON exam_results (teacher_id, subject_id, exam_name)",
    "CREATE INDEX IF NOT EXISTS ix_exam_results_student_id ON exam_results (student_id)",
    "CREATE INDEX IF NOT EXISTS ix_questions_teacher_id ON questions (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_coursewares_teacher_id ON coursewares (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_textbooks_teacher_id ON textbooks (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_textbook_chapters_textbook_id ON textbook_chapters (textbook_id)",
    "CREATE INDEX IF NOT EXISTS ix_homework_papers_teacher_id ON homework_papers (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_homework_questions_paper_id ON homework_questions (paper_id)",
]


async def _ensure_indexes():
    async with engine.begin() as conn:
        for sql in _INDEX_SQL:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（生产环境应使用 Alembic）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        await _ensure_indexes()
    except Exception:
        pass
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
    # 初始化知识图谱 Neo4j 约束/索引（best-effort，服务未就绪不阻塞启动）
    try:
        from app.core.neo4j_client import init_schema
        await init_schema()
    except Exception:
        pass
    yield
    await close_redis()
    try:
        from app.core.neo4j_client import close_neo4j
        from app.core.qdrant_client import close_qdrant
        await close_neo4j()
        await close_qdrant()
    except Exception:
        pass


app = FastAPI(
    title="AI 教育平台",
    description="AI 辅助教师日常教学工作平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=500)
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
app.include_router(interaction.router, prefix="/api/v1")
app.include_router(question_analysis.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(ws.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AI教育平台"}
