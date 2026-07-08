from sqlalchemy import String, Integer, ForeignKey, Text, Boolean
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class CoursewareSession(Base, TimestampMixin):
    """课堂互动会话：教师为某个课件开一个会话，生成分享码供学生作答。"""
    __tablename__ = "courseware_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    courseware_id: Mapped[int] = mapped_column(Integer, ForeignKey("coursewares.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否开放作答

    courseware = relationship("Courseware")
    records = relationship(
        "InteractionRecord", back_populates="session", cascade="all, delete-orphan"
    )


class InteractionRecord(Base, TimestampMixin):
    """学生在互动课件中的一次作答记录。"""
    __tablename__ = "interaction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courseware_sessions.id"), nullable=False, index=True
    )
    student_name: Mapped[str] = mapped_column(String(64), nullable=False)
    slide_index: Mapped[int] = mapped_column(Integer, default=0)
    component: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session = relationship("CoursewareSession", back_populates="records")
