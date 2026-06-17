from pydantic import BaseModel
from datetime import datetime
from app.models.question import QuestionType, DifficultyLevel


class QuestionOut(BaseModel):
    id: int
    question_type: QuestionType
    difficulty: DifficultyLevel
    content: str
    options: dict | None
    answer: str | None
    explanation: str | None
    subject_id: int
    grade_id: int
    tags: list | None
    created_at: datetime
    model_config = {"from_attributes": True}


class QuestionCreate(BaseModel):
    question_type: QuestionType
    difficulty: DifficultyLevel = DifficultyLevel.medium
    content: str
    options: dict | None = None
    answer: str | None = None
    explanation: str | None = None
    subject_id: int
    grade_id: int
    tags: list[str] | None = None


class QuestionFilter(BaseModel):
    subject_id: int | None = None
    grade_id: int | None = None
    question_type: QuestionType | None = None
    difficulty: DifficultyLevel | None = None
    keyword: str | None = None
    page: int = 1
    page_size: int = 20
