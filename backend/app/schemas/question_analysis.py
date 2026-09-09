from pydantic import BaseModel
from datetime import datetime

from app.models.textbook import ParseStatus
from app.models.question import QuestionType, DifficultyLevel


class AnalysisQuestionOut(BaseModel):
    id: int
    seq: int
    content: str
    options: dict | None = None
    answer: str | None = None
    question_type: QuestionType
    difficulty: DifficultyLevel
    selected: bool
    analysis_status: ParseStatus
    analysis_content: dict | None = None
    analysis_html: str | None = None
    analysis_source: str | None = None
    model_config = {"from_attributes": True}


class AnalysisSetOut(BaseModel):
    id: int
    name: str
    grade_id: int
    subject_id: int
    source_type: str
    parse_status: ParseStatus
    parse_error: str | None = None
    task_id: str | None = None
    question_count: int = 0
    created_at: datetime
    creator_name: str | None = None
    is_owner: bool = False
    can_edit: bool = False
    can_manage_collab: bool = False
    model_config = {"from_attributes": True}


class AnalysisSetDetail(AnalysisSetOut):
    questions: list[AnalysisQuestionOut] = []


class ManualImportIn(BaseModel):
    text: str
    grade_id: int
    subject_id: int
    name: str | None = None


class AnalyzeIn(BaseModel):
    question_ids: list[int]
    force: bool = False


class SaveToBankIn(BaseModel):
    question_ids: list[int]
