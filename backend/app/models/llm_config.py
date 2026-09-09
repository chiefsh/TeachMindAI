from sqlalchemy import String, Integer, ForeignKey, Boolean, Text, Float
from sqlalchemy.orm import mapped_column, Mapped
from app.core.database import Base
from app.models.base import TimestampMixin


class LLMConfig(Base, TimestampMixin):
    """全站系统大模型。teacher_id 恒为 NULL；历史个人配置启动时会迁走并删除。"""
    __tablename__ = "llm_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("teachers.id"), nullable=True, index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)       # openai/anthropic/qwen...
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)     # gpt-4o/claude-3-5...
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)   # 展示名称
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
