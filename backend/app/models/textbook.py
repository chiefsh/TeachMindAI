from sqlalchemy import String, Integer, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin
import enum


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class Textbook(Base, TimestampMixin):
    __tablename__ = "textbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)   # MinIO 路径
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)    # pdf/docx/epub...
    file_size: Mapped[int] = mapped_column(Integer, default=0)            # 字节
    parse_status: Mapped[ParseStatus] = mapped_column(
        SAEnum(ParseStatus), default=ParseStatus.pending
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)

    teacher = relationship("Teacher", back_populates="textbooks")
    subject = relationship("Subject")
    grade = relationship("Grade")
    chapters = relationship("TextbookChapter", back_populates="textbook", cascade="all, delete-orphan")
    images = relationship("TextbookImage", back_populates="textbook", cascade="all, delete-orphan")
    coursewares = relationship("Courseware", back_populates="textbook")


class TextbookChapter(Base):
    __tablename__ = "textbook_chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    textbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("textbooks.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("textbook_chapters.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)  # 标题层级 h1/h2/h3

    textbook = relationship("Textbook", back_populates="chapters")
    children = relationship("TextbookChapter", back_populates="parent")
    parent = relationship("TextbookChapter", back_populates="children", remote_side=[id])


class TextbookImage(Base):
    """从课本中提取的插图，供课件引用。"""
    __tablename__ = "textbook_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    textbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("textbooks.id"), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_name: Mapped[str] = mapped_column(String(512), nullable=False)  # MinIO 路径
    content_type: Mapped[str] = mapped_column(String(32), default="image/png")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 如「图4-17 电解水实验」

    textbook = relationship("Textbook", back_populates="images")
