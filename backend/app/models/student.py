from sqlalchemy import String, Integer, ForeignKey, Float, Enum as SAEnum, Text, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.textbook import ParseStatus
import enum


class EntryMethod(str, enum.Enum):
    manual = "manual"       # 手动录入
    document = "document"   # 文档导入
    image = "image"         # 图片OCR


class ReportType(str, enum.Enum):
    stats = "stats"   # 统计分析
    ai = "ai"         # AI 智能报告


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False)
    student_no: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    class_name: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 班级

    teacher = relationship("Teacher")
    grade = relationship("Grade")
    exam_results = relationship("ExamResult", back_populates="student", cascade="all, delete-orphan")


class ExamResult(Base, TimestampMixin):
    __tablename__ = "exam_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    exam_name: Mapped[str] = mapped_column(String(128), nullable=False)   # 考试名称
    score: Mapped[float] = mapped_column(Float, nullable=False)
    full_score: Mapped[float] = mapped_column(Float, default=100.0)
    entry_method: Mapped[EntryMethod] = mapped_column(SAEnum(EntryMethod), default=EntryMethod.manual)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    student = relationship("Student", back_populates="exam_results")
    teacher = relationship("Teacher")
    subject = relationship("Subject")


class GradeReport(Base, TimestampMixin):
    """成绩分析报告（统计分析 / AI 智能报告）历史记录。"""
    __tablename__ = "grade_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    grade_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("grades.id"), nullable=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    exam_name: Mapped[str] = mapped_column(String(128), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(SAEnum(ReportType), nullable=False)
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gen_status: Mapped[ParseStatus] = mapped_column(SAEnum(ParseStatus), default=ParseStatus.done)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    teacher = relationship("Teacher")
    subject = relationship("Subject")
    grade = relationship("Grade")
