import app.core.proxy  # noqa: F401  # 必须最先导入：清理 socks 代理，避免 litellm 崩溃
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "edu_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.file_tasks", "app.tasks.ai_tasks", "app.tasks.knowledge_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_queues={
        "ai_tasks": {"exchange": "ai_tasks", "routing_key": "ai"},
        "file_tasks": {"exchange": "file_tasks", "routing_key": "file"},
    },
    task_default_queue="file_tasks",
    task_routes={
        "app.tasks.ai_tasks.*": {"queue": "ai_tasks"},
        "app.tasks.file_tasks.*": {"queue": "file_tasks"},
        # 知识图谱任务同样重度依赖 LLM，并入 ai_tasks 队列，避免单独队列漏消费
        "app.tasks.knowledge_tasks.*": {"queue": "ai_tasks"},
    },
    result_expires=3600,
)
