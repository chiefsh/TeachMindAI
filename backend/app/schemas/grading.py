from datetime import date, datetime
from pydantic import BaseModel, Field


class AssignmentCreate(BaseModel):
    paper_id: int
    grade_id: int
    subject_id: int
    class_id: int | None = None
    class_name: str | None = None
    title: str | None = None
    assigned_at: date | None = None


class AssignmentOut(BaseModel):
    id: int
    paper_id: int
    paper_title: str = ""
    paper_type: str = "homework"
    title: str
    grade_id: int
    subject_id: int
    class_id: int | None = None
    class_name: str | None = None
    assigned_at: date
    status: str
    full_score: float | None = None
    student_count: int = 0
    submitted_count: int = 0
    graded_count: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}


class PaperQuestionOut(BaseModel):
    id: int
    sort_order: int
    content: str
    options: dict | None = None
    answer: str | None = None
    question_type: str | None = None
    score: float | int | None = None
    question_id: int | None = None
    source: str | None = None


class QuestionStatOut(BaseModel):
    paper_question_id: int
    sort_order: int
    content: str
    question_id: int | None = None
    error_count: int = 0
    blank_count: int = 0
    graded_count: int = 0
    error_rate: float = 0.0


class StudentRowOut(BaseModel):
    student_id: int
    name: str
    student_no: str
    class_name: str | None = None
    submission_id: int | None = None
    status: str = "pending"
    page_count: int = 0
    graded_count: int = 0
    question_count: int = 0
    total_score: float | None = None
    full_score: float | None = None


class AssignmentDetail(AssignmentOut):
    questions: list[PaperQuestionOut] = []
    question_stats: list[QuestionStatOut] = []
    students: list[StudentRowOut] = []


class PageOut(BaseModel):
    id: int
    page_index: int
    url: str
    file_name: str | None = None


class AnswerOut(BaseModel):
    id: int
    paper_question_id: int
    question_id: int | None = None
    student_answer: str | None = None
    verdict: str | None = None
    is_correct: bool | None = None
    score: float | None = None
    max_score: float | None = None
    comment: str | None = None
    grade_method: str = "manual"
    page_index: int | None = None


class SubmissionDetail(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    student_name: str = ""
    student_no: str = ""
    status: str
    total_score: float | None = None
    full_score: float | None = None
    paper_type: str = "homework"
    assignment_title: str = ""
    pages: list[PageOut] = []
    answers: list[AnswerOut] = []
    questions: list[PaperQuestionOut] = []
    roster: list[StudentRowOut] = []


class AnswerGradeIn(BaseModel):
    paper_question_id: int
    verdict: str | None = None  # correct / partial / wrong / blank / null 清除
    score: float | None = None
    comment: str | None = None
    student_answer: str | None = None
    page_index: int | None = None


class AnswerBatchIn(BaseModel):
    items: list[AnswerGradeIn] = Field(default_factory=list)


class PageOrderIn(BaseModel):
    page_ids: list[int]


class WrongItemOut(BaseModel):
    student_id: int | None = None
    student_name: str | None = None
    student_no: str | None = None
    assignment_id: int | None = None
    assignment_title: str | None = None
    paper_question_id: int | None = None
    question_id: int | None = None
    sort_order: int | None = None
    content: str = ""
    question_type: str | None = None
    error_count: int = 0
    blank_count: int = 0
    last_at: datetime | None = None
    use_count: int | None = None
