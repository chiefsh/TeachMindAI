from sqlalchemy import String, Integer, ForeignKey, Text, Enum as SAEnum, JSON, Boolean
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.textbook import ParseStatus
import enum


class CoursewareType(str, enum.Enum):
    standard = "standard"       # 标准课件
    interactive = "interactive" # 互动课件


class Courseware(Base, TimestampMixin):
    __tablename__ = "coursewares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    textbook_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("textbooks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    chapter_range: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"start":1,"end":3}
    page_range: Mapped[dict | None] = mapped_column(JSON, nullable=True)     # {"start":1,"end":20}
    courseware_type: Mapped[CoursewareType] = mapped_column(
        SAEnum(CoursewareType), default=CoursewareType.standard
    )
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)   # 教师自定义提示词
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)        # 幻灯片结构 JSON
    gen_status: Mapped[ParseStatus] = mapped_column(
        SAEnum(ParseStatus), default=ParseStatus.pending
    )
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)   # Celery task id
    is_interactive: Mapped[bool] = mapped_column(Boolean, default=False)

    teacher = relationship("Teacher", back_populates="coursewares")
    textbook = relationship("Textbook", back_populates="coursewares")
    homework_papers = relationship("HomeworkPaper", back_populates="courseware")
