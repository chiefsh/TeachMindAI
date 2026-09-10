from sqlalchemy import String, Integer, ForeignKey, Text, Enum as SAEnum, JSON, Boolean, Index, select
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.textbook import ParseStatus
import copy
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
    want_virtual_lab: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    virtual_lab_key: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 指定实验；空则自动匹配
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)        # 幻灯片结构 JSON
    gen_status: Mapped[ParseStatus] = mapped_column(
        SAEnum(ParseStatus), default=ParseStatus.pending
    )
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)   # Celery task id
    is_interactive: Mapped[bool] = mapped_column(Boolean, default=False)

    teacher = relationship("Teacher", back_populates="coursewares")
    textbook = relationship("Textbook", back_populates="coursewares")
    homework_papers = relationship("HomeworkPaper", back_populates="courseware")
    versions = relationship(
        "CoursewareVersion", back_populates="courseware", cascade="all, delete-orphan",
    )


class CoursewareVersion(Base, TimestampMixin):
    """一次生成（或重新生成前）的课件内容快照，不影响当前课件。"""
    __tablename__ = "courseware_versions"
    __table_args__ = (Index("ix_cw_versions_cw_id", "courseware_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    courseware_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("coursewares.id", ondelete="CASCADE"), nullable=False,
    )
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    render_style: Mapped[str] = mapped_column(String(16), nullable=False, default="html")
    theme: Mapped[str] = mapped_column(String(24), nullable=False, default="indigo")

    courseware = relationship("Courseware", back_populates="versions")
    teacher = relationship("Teacher")


def _render_style_value(cw: Courseware) -> str:
    rs = cw.render_style
    return rs.value if isinstance(rs, RenderStyle) else str(rs or "html")


def make_courseware_version(cw: Courseware, teacher_id: int) -> "CoursewareVersion | None":
    if not isinstance(cw.content, dict):
        return None
    return CoursewareVersion(
        courseware_id=cw.id,
        teacher_id=teacher_id,
        title=cw.title,
        content=copy.deepcopy(cw.content),
        render_style=_render_style_value(cw),
        theme=cw.theme or "indigo",
    )


async def save_courseware_version(db, cw: Courseware, teacher_id: int, *, skip_if_same: bool = True):
    """把当前课件内容存成一版。内容与最近一版完全相同则跳过。"""
    ver = make_courseware_version(cw, teacher_id)
    if ver is None:
        return None
    if skip_if_same:
        last = (
            await db.execute(
                select(CoursewareVersion)
                .where(CoursewareVersion.courseware_id == cw.id)
                .order_by(CoursewareVersion.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if (
            last
            and last.title == ver.title
            and last.render_style == ver.render_style
            and last.theme == ver.theme
            and last.content == ver.content
        ):
            return None
    db.add(ver)
    return ver
