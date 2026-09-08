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
from app.api.v1 import auth, education, textbook, question, courseware, homework, student, settings, ws, dashboard, interaction, question_analysis, knowledge, share


# create_all 不会给已有表补索引，启动时幂等补齐热查询字段
_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_students_teacher_id ON students (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_students_teacher_grade ON students (teacher_id, grade_id)",
    "CREATE INDEX IF NOT EXISTS ix_exam_results_teacher_id ON exam_results (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_exam_results_teacher_subject_exam ON exam_results (teacher_id, subject_id, exam_name)",
    "CREATE INDEX IF NOT EXISTS ix_exam_results_student_id ON exam_results (student_id)",
    "CREATE INDEX IF NOT EXISTS ix_questions_teacher_id ON questions (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_questions_teacher_content_hash ON questions (teacher_id, content_hash)",
    "CREATE INDEX IF NOT EXISTS ix_coursewares_teacher_id ON coursewares (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_textbooks_teacher_id ON textbooks (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_textbook_chapters_textbook_id ON textbook_chapters (textbook_id)",
    "CREATE INDEX IF NOT EXISTS ix_homework_papers_teacher_id ON homework_papers (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_homework_papers_textbook_id ON homework_papers (textbook_id)",
    "CREATE INDEX IF NOT EXISTS ix_question_imports_teacher_id ON question_imports (teacher_id)",
]


# create_all 也不会给已有表补列，启动时按需补齐后加的字段
_COLUMN_SQL = [
    (
        "coursewares", "render_style",
        "ALTER TABLE coursewares ADD COLUMN render_style VARCHAR(16) NOT NULL DEFAULT 'ppt'",
    ),
    (
        "coursewares", "theme",
        "ALTER TABLE coursewares ADD COLUMN theme VARCHAR(24) NOT NULL DEFAULT 'indigo'",
    ),
    (
        "questions", "images",
        "ALTER TABLE questions ADD COLUMN images JSON NULL",
    ),
    (
        "questions", "content_hash",
        "ALTER TABLE questions ADD COLUMN content_hash VARCHAR(64) NULL",
    ),
    (
        "questions", "use_count",
        "ALTER TABLE questions ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "questions", "analysis_content",
        "ALTER TABLE questions ADD COLUMN analysis_content JSON NULL",
    ),
    (
        "questions", "analysis_html",
        "ALTER TABLE questions ADD COLUMN analysis_html TEXT NULL",
    ),
    (
        "analysis_questions", "analysis_source",
        "ALTER TABLE analysis_questions ADD COLUMN analysis_source VARCHAR(16) NULL",
    ),
    (
        "homework_papers", "source_type",
        "ALTER TABLE homework_papers ADD COLUMN source_type VARCHAR(16) NOT NULL DEFAULT 'courseware'",
    ),
    (
        "homework_papers", "question_source",
        "ALTER TABLE homework_papers ADD COLUMN question_source VARCHAR(16) NOT NULL DEFAULT 'ai'",
    ),
    (
        "homework_papers", "textbook_id",
        "ALTER TABLE homework_papers ADD COLUMN textbook_id INTEGER NULL",
    ),
    (
        "homework_papers", "chapter_ids",
        "ALTER TABLE homework_papers ADD COLUMN chapter_ids JSON NULL",
    ),
    (
        "homework_papers", "courseware_ids",
        "ALTER TABLE homework_papers ADD COLUMN courseware_ids JSON NULL",
    ),
    (
        "homework_questions", "source",
        "ALTER TABLE homework_questions ADD COLUMN source VARCHAR(16) NULL",
    ),
]


async def _ensure_indexes():
    async with engine.begin() as conn:
        for sql in _INDEX_SQL:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass


async def _ensure_columns():
    from sqlalchemy import inspect as sa_inspect

    async with engine.begin() as conn:
        for table, column, ddl in _COLUMN_SQL:
            try:
                columns = await conn.run_sync(
                    lambda sync_conn, t=table: [c["name"] for c in sa_inspect(sync_conn).get_columns(t)]
                )
                if column not in columns:
                    await conn.execute(text(ddl))
            except Exception:
                pass
        # 作业题分值改为可空（作业不记分）
        try:
            await conn.execute(text("ALTER TABLE homework_questions MODIFY COLUMN score INT NULL"))
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
    try:
        await _ensure_columns()
    except Exception:
        pass
    try:
        from app.services.question_bank_service import backfill_question_bank_meta
        await backfill_question_bank_meta()
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
    title="智课星",
    description="智课星 · AI 辅助教师日常教学工作平台",
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
app.include_router(share.router, prefix="/api/v1")
app.include_router(ws.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "智课星"}
