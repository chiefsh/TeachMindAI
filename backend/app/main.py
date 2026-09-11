import app.core.proxy  # noqa: F401  # 必须最先导入：清理 socks 代理，避免 litellm 崩溃
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.database import engine, Base
from app.core.redis_client import close_redis
from app.core.minio_client import init_buckets
from app.core.seed import seed_education_data, seed_subject_prompts, seed_rbac_data
from app.api.v1 import auth, education, textbook, question, courseware, homework, student, settings, ws, dashboard, interaction, question_analysis, knowledge, share, grading, classroom, rbac, animation


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
    "CREATE INDEX IF NOT EXISTS ix_coursewares_created_at ON coursewares (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_cw_versions_cw_id ON courseware_versions (courseware_id)",
    "CREATE INDEX IF NOT EXISTS ix_textbooks_teacher_id ON textbooks (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_textbook_chapters_textbook_id ON textbook_chapters (textbook_id)",
    "CREATE INDEX IF NOT EXISTS ix_homework_papers_teacher_id ON homework_papers (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_homework_papers_textbook_id ON homework_papers (textbook_id)",
    "CREATE INDEX IF NOT EXISTS ix_question_imports_teacher_id ON question_imports (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_grading_assignments_teacher_id ON grading_assignments (teacher_id)",
    "CREATE INDEX IF NOT EXISTS ix_paper_submissions_teacher_id ON paper_submissions (teacher_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_grading_assignments_collect_token ON grading_assignments (collect_token)",
    "CREATE INDEX IF NOT EXISTS ix_teachers_org_id ON teachers (org_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_class_grade_name ON school_classes (grade_id, name)",
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
        "coursewares", "want_virtual_lab",
        "ALTER TABLE coursewares ADD COLUMN want_virtual_lab TINYINT(1) NOT NULL DEFAULT 0",
    ),
    (
        "coursewares", "virtual_lab_key",
        "ALTER TABLE coursewares ADD COLUMN virtual_lab_key VARCHAR(64) NULL",
    ),
    (
        "coursewares", "animation_keys",
        "ALTER TABLE coursewares ADD COLUMN animation_keys JSON NULL",
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
    (
        "homework_questions", "question_type",
        "ALTER TABLE homework_questions ADD COLUMN question_type VARCHAR(32) NULL",
    ),
    (
        "homework_papers", "grade_id",
        "ALTER TABLE homework_papers ADD COLUMN grade_id INTEGER NULL",
    ),
    (
        "homework_papers", "subject_id",
        "ALTER TABLE homework_papers ADD COLUMN subject_id INTEGER NULL",
    ),
    (
        "questions", "wrong_count",
        "ALTER TABLE questions ADD COLUMN wrong_count INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "students", "class_id",
        "ALTER TABLE students ADD COLUMN class_id INTEGER NULL",
    ),
    (
        "grading_assignments", "class_id",
        "ALTER TABLE grading_assignments ADD COLUMN class_id INTEGER NULL",
    ),
    (
        "grading_assignments", "collect_token",
        "ALTER TABLE grading_assignments ADD COLUMN collect_token VARCHAR(48) NULL",
    ),
    (
        "teachers", "org_id",
        "ALTER TABLE teachers ADD COLUMN org_id INTEGER NULL",
    ),
    (
        "teachers", "is_super",
        "ALTER TABLE teachers ADD COLUMN is_super TINYINT(1) NOT NULL DEFAULT 0",
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
        # 系统大模型：teacher_id 改为可空
        try:
            await conn.execute(text("ALTER TABLE llm_configs MODIFY COLUMN teacher_id INTEGER NULL"))
        except Exception:
            pass


async def _migrate_llm_configs_to_system():
    """把历史个人 LLM 配置收成全站系统配置，并删除其余个人行。"""
    from sqlalchemy import delete, select
    from app.core.database import AsyncSessionLocal
    from app.models.llm_config import LLMConfig
    from app.models.teacher import Teacher

    async with AsyncSessionLocal() as db:
        has_sys = (
            await db.execute(
                select(LLMConfig.id).where(LLMConfig.teacher_id.is_(None)).limit(1)
            )
        ).scalar()
        if not has_sys:
            super_id = (
                await db.execute(select(Teacher.id).where(Teacher.is_super.is_(True)))
            ).scalar()
            source_tid = None
            if super_id:
                n = (
                    await db.execute(
                        select(LLMConfig.id)
                        .where(LLMConfig.teacher_id == super_id)
                        .limit(1)
                    )
                ).scalar()
                if n:
                    source_tid = super_id
            if not source_tid:
                source_tid = (
                    await db.execute(
                        select(LLMConfig.teacher_id)
                        .where(LLMConfig.teacher_id.is_not(None))
                        .order_by(LLMConfig.id)
                        .limit(1)
                    )
                ).scalar()
            if source_tid:
                rows = (
                    await db.execute(
                        select(LLMConfig).where(LLMConfig.teacher_id == source_tid)
                    )
                ).scalars().all()
                for r in rows:
                    r.teacher_id = None
                await db.flush()
        await db.execute(delete(LLMConfig).where(LLMConfig.teacher_id.is_not(None)))
        sys_rows = (
            await db.execute(select(LLMConfig).where(LLMConfig.teacher_id.is_(None)))
        ).scalars().all()
        defaults = [r for r in sys_rows if r.is_default]
        if len(defaults) > 1:
            for r in defaults[1:]:
                r.is_default = False
        elif not defaults and sys_rows:
            sys_rows[0].is_default = True
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（生产环境应使用 Alembic）
    import app.models  # noqa: F401  # 注册全部模型到 metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        await _ensure_columns()
    except Exception:
        pass
    try:
        await _ensure_indexes()
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
    try:
        await seed_rbac_data()
    except Exception:
        pass
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.animation_service import ensure_system_labs
        async with AsyncSessionLocal() as _adb:
            await ensure_system_labs(_adb)
    except Exception:
        pass
    try:
        await _migrate_llm_configs_to_system()
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
    title="知序台",
    description="知序台 · 让知识与教学变得有序",
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
app.include_router(animation.router, prefix="/api/v1")
app.include_router(homework.router, prefix="/api/v1")
app.include_router(grading.router, prefix="/api/v1")
app.include_router(grading.public_router, prefix="/api/v1")
app.include_router(student.router, prefix="/api/v1")
app.include_router(classroom.router, prefix="/api/v1")
app.include_router(rbac.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(interaction.router, prefix="/api/v1")
app.include_router(question_analysis.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(share.router, prefix="/api/v1")
app.include_router(ws.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "知序台"}
