from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "AI教育平台"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    ALGORITHM: str = "HS256"

    # 数据库
    DATABASE_URL: str = "mysql+aiomysql://edu_user:edu_pass@localhost:3306/edu_platform"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # RabbitMQ / Celery
    RABBITMQ_URL: str = "amqp://edu_user:edu_pass@localhost:5672/"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "edu_minio_user"
    MINIO_SECRET_KEY: str = "edu_minio_pass"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_TEXTBOOKS: str = "textbooks"
    MINIO_BUCKET_QUESTIONS: str = "question-banks"
    MINIO_BUCKET_COURSEWARES: str = "coursewares"

    # AES加密（用于LLM API Key存储）
    ENCRYPTION_KEY: str = "edu-platform-32-byte-encrypt-key"

    # 文档解析 / OCR（liteparse）
    OCR_LANGUAGE: str = "chi_sim"         # Tesseract 语言；多语言用 + 连接（需本地均有对应 .traineddata）
    OCR_TESSDATA_PATH: str = ""            # 留空则自动探测系统 tessdata 目录

    # 课本整页截图（增强扫描版/图多文字少页面的课件配图）
    TEXTBOOK_PAGE_SCREENSHOT: bool = True       # 是否对扫描页渲染整页截图入库
    TEXTBOOK_PAGE_SCREENSHOT_MAX: int = 40      # 单本课本最多截图页数
    TEXTBOOK_SCAN_TEXT_THRESHOLD: int = 50      # 页面文本少于该字符数视为扫描/图多页

    model_config = {"env_file": ".env", "extra": "ignore"}

    def model_post_init(self, __context):
        if not self.CELERY_BROKER_URL:
            object.__setattr__(self, "CELERY_BROKER_URL", self.RABBITMQ_URL)
        if not self.CELERY_RESULT_BACKEND:
            object.__setattr__(self, "CELERY_RESULT_BACKEND", self.REDIS_URL)


settings = Settings()
