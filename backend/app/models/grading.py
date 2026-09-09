"""纸质作业/试卷批改：一次布置、学生原卷页图、逐题给分、错题流水。"""
from datetime import date
from sqlalchemy import (
    String, Integer, ForeignKey, Text, Date, Float, Boolean,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class GradingAssignment(Base, TimestampMixin):
    """某一次作业或考试的布置（班级 + 日期），卷面来自 HomeworkPaper。"""
    __tablename__ = "grading_assignments"
    __table_args__ = (
        Index("ix_grading_assignments_teacher_id", "teacher_id"),
        Index("ix_grading_assignments_paper_id", "paper_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    paper_id: Mapped[int] = mapped_column(Integer, ForeignKey("homework_papers.id"), nullable=False)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    class_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("school_classes.id"), nullable=True, index=True)
    class_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    assigned_at: Mapped[date] = mapped_column(Date, nullable=False)
    # collecting / grading / done
    status: Mapped[str] = mapped_column(String(16), default="collecting", server_default="collecting")
    full_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    collect_token: Mapped[str | None] = mapped_column(String(48), nullable=True, unique=True, index=True)

    paper = relationship("HomeworkPaper")
    submissions = relationship(
        "PaperSubmission", back_populates="assignment", cascade="all, delete-orphan",
    )
    wrong_logs = relationship("WrongQuestionLog", back_populates="assignment")


class PaperSubmission(Base, TimestampMixin):
    """某个学生这一次布置的纸质答卷。"""
    __tablename__ = "paper_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_submission_assignment_student"),
        Index("ix_paper_submissions_teacher_id", "teacher_id"),
        Index("ix_paper_submissions_student_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grading_assignments.id", ondelete="CASCADE"), nullable=False,
    )
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    # pending / submitted / graded
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    full_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    assignment = relationship("GradingAssignment", back_populates="submissions")
    student = relationship("Student")
    pages = relationship(
        "SubmissionPage",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionPage.page_index",
    )
    answers = relationship(
        "SubmissionAnswer",
        back_populates="submission",
        cascade="all, delete-orphan",
    )


class SubmissionPage(Base, TimestampMixin):
    """答卷的一页原图（拍照或从 PDF 渲染）。"""
    __tablename__ = "submission_pages"
    __table_args__ = (
        Index("ix_submission_pages_submission_id", "submission_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("paper_submissions.id", ondelete="CASCADE"), nullable=False,
    )
    page_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), default="image/jpeg")
    file_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    submission = relationship("PaperSubmission", back_populates="pages")


class SubmissionAnswer(Base, TimestampMixin):
    """该生该题的批改结果。verdict: correct / partial / wrong / blank，空表示未批。"""
    __tablename__ = "submission_answers"
    __table_args__ = (
        UniqueConstraint("submission_id", "paper_question_id", name="uq_answer_submission_question"),
        Index("ix_submission_answers_question_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("paper_submissions.id", ondelete="CASCADE"), nullable=False,
    )
    paper_question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("homework_questions.id"), nullable=False,
    )
    question_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("questions.id"), nullable=True,
    )
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade_method: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")
    page_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    submission = relationship("PaperSubmission", back_populates="answers")
    paper_question = relationship("HomeworkQuestion")
    wrong_log = relationship(
        "WrongQuestionLog",
        back_populates="answer",
        uselist=False,
        cascade="all, delete-orphan",
    )


class WrongQuestionLog(Base, TimestampMixin):
    """错题流水：一题一次作答最多一笔，改判时更新或删除。"""
    __tablename__ = "wrong_question_logs"
    __table_args__ = (
        UniqueConstraint("submission_answer_id", name="uq_wrong_log_answer"),
        Index("ix_wrong_logs_teacher_question", "teacher_id", "question_id"),
        Index("ix_wrong_logs_assignment_pq", "assignment_id", "paper_question_id"),
        Index("ix_wrong_logs_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grading_assignments.id", ondelete="CASCADE"), nullable=False,
    )
    paper_id: Mapped[int] = mapped_column(Integer, ForeignKey("homework_papers.id"), nullable=False)
    paper_question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("homework_questions.id"), nullable=False,
    )
    question_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("questions.id"), nullable=True,
    )
    submission_answer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("submission_answers.id", ondelete="CASCADE"), nullable=False,
    )
    is_blank: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    assignment = relationship("GradingAssignment", back_populates="wrong_logs")
    answer = relationship("SubmissionAnswer", back_populates="wrong_log")
