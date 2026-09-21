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


class HomeworkSourceType(str, enum.Enum):
    courseware = "courseware"   # 按课件
    textbook = "textbook"       # 整本课本
    chapters = "chapters"       # 指定章节


class QuestionSource(str, enum.Enum):
    ai = "ai"         # 仅 AI 生成
    bank = "bank"     # 仅题库（不够时回退 AI）
    mixed = "mixed"   # 题库优先，缺口用 AI 补


class ReviewStatus(str, enum.Enum):
    unreviewed = "unreviewed"  # 生成后待教师校对
    verified = "verified"      # 教师确认题与答案可用


class HomeworkPaper(Base, TimestampMixin):
    __tablename__ = "homework_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    courseware_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("coursewares.id"), nullable=True)
    courseware_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    textbook_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("textbooks.id"), nullable=True)
    chapter_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(16), default=HomeworkSourceType.courseware.value, server_default="courseware",
    )
    question_source: Mapped[str] = mapped_column(
        String(16), default=QuestionSource.ai.value, server_default="ai",
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    grade_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("grades.id"), nullable=True, index=True)
    subject_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=True, index=True)
    paper_type: Mapped[HomeworkType] = mapped_column(SAEnum(HomeworkType), default=HomeworkType.homework)
    difficulty: Mapped[DifficultyLevel] = mapped_column(SAEnum(DifficultyLevel), default=DifficultyLevel.medium)
    question_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 旧 {"single_choice":5}；新 {"difficulty_mode","items":[{"type","count","ratios"}]}
    gen_status: Mapped[ParseStatus] = mapped_column(SAEnum(ParseStatus), default=ParseStatus.pending)
    review_status: Mapped[str] = mapped_column(
        String(16), default=ReviewStatus.unreviewed.value, server_default="unreviewed",
    )
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)   # 生成的完整试卷内容

    teacher = relationship("Teacher")
    courseware = relationship("Courseware", back_populates="homework_papers")
    textbook = relationship("Textbook")
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
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 考试有分；作业为 null
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)  # ai | bank
    check_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # passed | unchecked | bank

    paper = relationship("HomeworkPaper", back_populates="questions")
    question = relationship("Question")
