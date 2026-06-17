from pydantic import BaseModel
from datetime import datetime
from app.models.textbook import ParseStatus
from app.models.homework import HomeworkType
from app.models.question import DifficultyLevel, QuestionType


class HomeworkCreate(BaseModel):
    courseware_ids: list[int]
    title: str
    paper_type: HomeworkType = HomeworkType.homework
    difficulty: DifficultyLevel = DifficultyLevel.medium
    question_config: dict      # {"single_choice":5,"fill_blank":3,"short_answer":2}
    use_question_bank: bool = False  # True=从题库筛选, False=AI直接生成


class HomeworkOut(BaseModel):
    id: int
    title: str
    paper_type: HomeworkType
    difficulty: DifficultyLevel
    gen_status: ParseStatus
    courseware_id: int | None
    created_at: datetime
    model_config = {"from_attributes": True}


class HomeworkQuestionOut(BaseModel):
    id: int
    sort_order: int
    content: str
    options: dict | None = None
    answer: str | None = None
    score: float | int | None = None
    model_config = {"from_attributes": True}


class HomeworkDetail(HomeworkOut):
    content: str | None
    question_config: dict | None
    questions: list[HomeworkQuestionOut] = []
