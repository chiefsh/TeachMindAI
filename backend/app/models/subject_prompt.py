from sqlalchemy import String, Integer, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped
from app.core.database import Base
from app.models.base import TimestampMixin


class SubjectPromptTemplate(Base, TimestampMixin):
    """科目专属的课件生成提示词模板。

    - teacher_id 为空：系统内置默认模板（由 seed 写入）。
    - teacher_id 非空：教师对某科目的个性化覆盖。
    按 subject_name 归类（同名科目跨学段共用一份），生成课件时按
    「教师覆盖 > 系统默认」的顺序解析。
    """
    __tablename__ = "subject_prompt_templates"
    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_name", name="uq_teacher_subject_prompt"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_name: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)              # 教学侧重
    interactive_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)  # 适合的互动/HTML 形式
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
