from sqlalchemy import String, Integer, ForeignKey, Text, Enum as SAEnum, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.textbook import ParseStatus
from app.models.question import DifficultyLevel
import enum


class HomeworkType(str, enum.Enum):
    homework = "homework"   # 课后作业
    exam = "exam"           # 考试试卷


class HomeworkPaper(Base, TimestampMixin):
    __tablename__ = "homework_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    courseware_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("coursewares.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    paper_type: Mapped[HomeworkType] = mapped_column(SAEnum(HomeworkType), default=HomeworkType.homework)
    difficulty: Mapped[DifficultyLevel] = mapped_column(SAEnum(DifficultyLevel), default=DifficultyLevel.medium)
    question_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # {"single_choice":5,"fill_blank":3,"short_answer":2}
    gen_status: Mapped[ParseStatus] = mapped_column(SAEnum(ParseStatus), default=ParseStatus.pending)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)   # 生成的完整试卷内容

    teacher = relationship("Teacher")
    courseware = relationship("Courseware", back_populates="homework_papers")
    questions = relationship("HomeworkQuestion", back_populates="paper", cascade="all, delete-orphan")


class HomeworkQuestion(Base):
    __tablename__ = "homework_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(Integer, ForeignKey("homework_papers.id"), nullable=False)
    question_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("questions.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)   # 题目内容（题库题或AI生成题）
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=10)      # 分值

    paper = relationship("HomeworkPaper", back_populates="questions")
    question = relationship("Question")
