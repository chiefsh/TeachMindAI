from sqlalchemy import String, Integer, ForeignKey, Text, Enum as SAEnum, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.textbook import ParseStatus
import enum


class QuestionType(str, enum.Enum):
    single_choice = "single_choice"   # 单选题
    multi_choice = "multi_choice"     # 多选题
    fill_blank = "fill_blank"         # 填空题
    short_answer = "short_answer"     # 简答题
    essay = "essay"                   # 论述/作文
    true_false = "true_false"         # 判断题
    calculation = "calculation"       # 计算题


class DifficultyLevel(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"
    very_hard = "very_hard"


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False, index=True)
    question_type: Mapped[QuestionType] = mapped_column(SAEnum(QuestionType), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        SAEnum(DifficultyLevel), default=DifficultyLevel.medium
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)          # 题干
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # {"A":"...","B":"..."}
    # {"stem":["teacher/qimg/x.png"], "options":{"A":"teacher/qimg/a.png"}}
    images: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)     # 答案
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)# 解析
    source_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 来源文件
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)      # 知识点标签

    teacher = relationship("Teacher", back_populates="questions")
    subject = relationship("Subject")
    grade = relationship("Grade")


class QuestionImport(Base, TimestampMixin):
    """题库文件导入记录。"""
    __tablename__ = "question_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(16), default=ParseStatus.pending.value)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
