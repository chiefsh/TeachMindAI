"""试题分析模块模型：一次导入的试题批次 + 批次下每道题（含 AI 解析）。"""
from sqlalchemy import String, Integer, Text, JSON, ForeignKey, Boolean, Enum as SAEnum
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.textbook import ParseStatus
from app.models.question import QuestionType, DifficultyLevel


class AnalysisSet(Base, TimestampMixin):
    """一次导入的试题批次（试卷/若干题）。"""
    __tablename__ = "analysis_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)         # 试题名称
    source_type: Mapped[str] = mapped_column(String(16), default="manual")  # manual/file/image
    source_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parse_status: Mapped[ParseStatus] = mapped_column(SAEnum(ParseStatus), default=ParseStatus.pending)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    questions = relationship(
        "AnalysisQuestion", back_populates="analysis_set",
        cascade="all, delete-orphan", order_by="AnalysisQuestion.seq",
    )


class AnalysisQuestion(Base, TimestampMixin):
    """批次下的一道题目及其 AI 解析结果。"""
    __tablename__ = "analysis_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    set_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_sets.id"), nullable=False, index=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, default=0)                    # 题序
    content: Mapped[str] = mapped_column(Text, nullable=False)              # 题干
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)       # {"A":"..."}
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)         # 答案
    question_type: Mapped[QuestionType] = mapped_column(SAEnum(QuestionType), default=QuestionType.short_answer)
    difficulty: Mapped[DifficultyLevel] = mapped_column(SAEnum(DifficultyLevel), default=DifficultyLevel.medium)

    selected: Mapped[bool] = mapped_column(Boolean, default=False)          # 是否勾选做 AI 解析
    analysis_status: Mapped[ParseStatus] = mapped_column(SAEnum(ParseStatus), default=ParseStatus.pending)
    analysis_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {思路,steps,知识点,易错点,答案}
    analysis_html: Mapped[str | None] = mapped_column(Text, nullable=True)      # 图解 HTML（在线渲染）

    analysis_set = relationship("AnalysisSet", back_populates="questions")
