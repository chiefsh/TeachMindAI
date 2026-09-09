from sqlalchemy import String, Integer, ForeignKey, Float, Enum as SAEnum, Text, JSON, UniqueConstraint, Index
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


class SchoolClass(Base, TimestampMixin):
    """教师名下的行政班（某年级的一个班）。"""
    __tablename__ = "school_classes"
    __table_args__ = (
        UniqueConstraint("teacher_id", "grade_id", "name", name="uq_class_teacher_grade_name"),
        Index("ix_school_classes_teacher_id", "teacher_id"),
        Index("ix_school_classes_grade_id", "grade_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)

    teacher = relationship("Teacher")
    grade = relationship("Grade")
    students = relationship("Student", back_populates="school_class")


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False, index=True)
    class_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("school_classes.id"), nullable=True, index=True,
    )
    student_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    class_name: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 与班级名称同步，兼容旧查询

    teacher = relationship("Teacher")
    grade = relationship("Grade")
    school_class = relationship("SchoolClass", back_populates="students")
    exam_results = relationship("ExamResult", back_populates="student", cascade="all, delete-orphan")


class ExamResult(Base, TimestampMixin):
    __tablename__ = "exam_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    exam_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)   # 考试名称
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
