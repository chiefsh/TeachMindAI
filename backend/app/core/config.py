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

    model_config = {"env_file": ".env", "extra": "ignore"}

    def model_post_init(self, __context):
        if not self.CELERY_BROKER_URL:
            object.__setattr__(self, "CELERY_BROKER_URL", self.RABBITMQ_URL)
        if not self.CELERY_RESULT_BACKEND:
            object.__setattr__(self, "CELERY_RESULT_BACKEND", self.REDIS_URL)


settings = Settings()
