from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class SchoolLevel(Base):
    __tablename__ = "school_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)  # 小学/初中/高中
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    grades = relationship("Grade", back_populates="school_level")
    subjects = relationship("Subject", back_populates="school_level")


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_level_id: Mapped[int] = mapped_column(Integer, ForeignKey("school_levels.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(16), nullable=False)  # 一年级/七年级/高一
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    school_level = relationship("SchoolLevel", back_populates="grades")
    teacher_subjects = relationship("TeacherSubject", back_populates="grade")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_level_id: Mapped[int] = mapped_column(Integer, ForeignKey("school_levels.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)  # 语文/数学/英语
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    school_level = relationship("SchoolLevel", back_populates="subjects")
    teacher_subjects = relationship("TeacherSubject", back_populates="subject")


class TeacherSubject(Base, TimestampMixin):
    """教师-学段-年级-科目 多对多关联"""
    __tablename__ = "teacher_subjects"
    __table_args__ = (
        UniqueConstraint("teacher_id", "grade_id", "subject_id", name="uq_teacher_grade_subject"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)

    teacher = relationship("Teacher", back_populates="subjects")
    grade = relationship("Grade", back_populates="teacher_subjects")
    subject = relationship("Subject", back_populates="teacher_subjects")
