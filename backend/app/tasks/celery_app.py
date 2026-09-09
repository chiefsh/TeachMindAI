import app.core.proxy  # noqa: F401  # 必须最先导入：清理 socks 代理，避免 litellm 崩溃
from celery import Celery
from app.core.config import settings

FAST_QUEUE = "fast_tasks"
SLOW_QUEUE = "slow_tasks"

celery_app = Celery(
    "edu_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.file_tasks", "app.tasks.ai_tasks", "app.tasks.knowledge_tasks"],
)

# 快通道：单页优化、OCR、小文件导入等短任务，避免被整份生成堵住。
# 慢通道：整份课件/作业、整书解析、试题分析、知识图谱抽取。
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    task_queues={
        FAST_QUEUE: {"exchange": FAST_QUEUE, "routing_key": "fast"},
        SLOW_QUEUE: {"exchange": SLOW_QUEUE, "routing_key": "slow"},
    },
    task_default_queue=SLOW_QUEUE,
    # 必须用 dict：元组会被当成多张路由表，投递时 MapRoute 拆包报错。
    # 精确任务名优先于通配符，因此快通道条目不会落到 * 的慢队列。
    task_routes={
        "app.tasks.ai_tasks.optimize_courseware_slide_task": {"queue": FAST_QUEUE},
        "app.tasks.ai_tasks.ocr_grades_task": {"queue": FAST_QUEUE},
        "app.tasks.file_tasks.parse_question_file_task": {"queue": FAST_QUEUE},
        "app.tasks.file_tasks.parse_analysis_file_task": {"queue": FAST_QUEUE},
        "app.tasks.file_tasks.import_grades_task": {"queue": FAST_QUEUE},
        "app.tasks.ai_tasks.*": {"queue": SLOW_QUEUE},
        "app.tasks.file_tasks.*": {"queue": SLOW_QUEUE},
        "app.tasks.knowledge_tasks.*": {"queue": SLOW_QUEUE},
    },
    result_expires=3600,
)
