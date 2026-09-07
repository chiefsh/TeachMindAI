from sqlalchemy import String, Integer, ForeignKey, Text, Enum as SAEnum, JSON, Boolean
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.textbook import ParseStatus
import enum


class CoursewareType(str, enum.Enum):
    standard = "standard"       # 标准课件
    interactive = "interactive" # 互动课件


class RenderStyle(str, enum.Enum):
    ppt = "ppt"     # 幻灯片样式：演示模式 + 导出 PPT
    html = "html"   # 网页样式：单页滚动网页课件


class Courseware(Base, TimestampMixin):
    __tablename__ = "coursewares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    textbook_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("textbooks.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    chapter_range: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"chapter_ids":[12,15,18]}
    page_range: Mapped[dict | None] = mapped_column(JSON, nullable=True)     # {"start":1,"end":20}
    courseware_type: Mapped[CoursewareType] = mapped_column(
        SAEnum(CoursewareType), default=CoursewareType.standard
    )
    render_style: Mapped[RenderStyle] = mapped_column(
        SAEnum(RenderStyle, native_enum=False, length=16),
        default=RenderStyle.ppt,
        server_default=RenderStyle.ppt.value,
    )
    # 视觉主题 key，见 services/courseware_theme.py；旧值 indigo 等会映射到现行主题
    theme: Mapped[str] = mapped_column(String(24), default="indigo", server_default="indigo")
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
