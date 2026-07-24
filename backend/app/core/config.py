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
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

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

    # ── 知识图谱 ──────────────────────────────────────────────
    KG_ENABLED: bool = True
    # 图数据库 Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "edu_neo4j_pass"
    NEO4J_DATABASE: str = "neo4j"
    # 向量数据库 Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    KG_COLLECTION: str = "knowledge_points"
    # 知识点语义去重阈值（余弦相似度，命中则视为同一知识点）
    KG_DEDUP_THRESHOLD: float = 0.88
    # 向量嵌入（留空 EMBEDDING_MODEL 则禁用向量去重，退化为按名称精确匹配）
    EMBEDDING_MODEL: str = ""
    EMBEDDING_API_BASE: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_DIM: int = 1024

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
