from datetime import datetime

from sqlalchemy import String, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ShareLink(Base, TimestampMixin):
    """课件 / 试题分析的免登录分享链接。"""
    __tablename__ = "share_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    teacher = relationship("Teacher")
