from sqlalchemy import String, Integer, ForeignKey, Text, JSON, Index
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class InteractiveAsset(Base, TimestampMixin):
    """可复用互动动画：系统预置实验台 + 教师另存。"""
    __tablename__ = "interactive_assets"
    __table_args__ = (
        Index("ix_anim_subject_group", "subject", "group"),
        Index("ix_anim_teacher_id", "teacher_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    subject: Mapped[str] = mapped_column(String(32), default="化学", server_default="化学")
    group: Mapped[str] = mapped_column(String(64), default="", server_default="")
    kind: Mapped[str] = mapped_column(String(32), default="chem_lab", server_default="chem_lab")
    origin: Mapped[str] = mapped_column(String(16), default="system", server_default="system")
    teacher_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    knowledge_tags: Mapped[list] = mapped_column(JSON, default=list)
    skill: Mapped[str] = mapped_column(String(64), default="edu-chem-lab", server_default="edu-chem-lab")
    problem_type: Mapped[str] = mapped_column(String(64), nullable=False)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    html: Mapped[str | None] = mapped_column(MEDIUMTEXT, nullable=True)

    teacher = relationship("Teacher")
