from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from app.models.textbook import ParseStatus
from app.models.homework import HomeworkType, HomeworkSourceType, QuestionSource
from app.models.question import DifficultyLevel


class HomeworkCreate(BaseModel):
    title: str
    paper_type: HomeworkType = HomeworkType.homework
    difficulty: DifficultyLevel = DifficultyLevel.medium
    # 旧：{"single_choice":5}  新：{"difficulty_mode":"overall|per_type","items":[{"type","count","ratios"}]}
    question_config: dict
    source_type: HomeworkSourceType = HomeworkSourceType.courseware
    question_source: QuestionSource = QuestionSource.ai
    courseware_ids: list[int] = Field(default_factory=list)
    textbook_id: int | None = None
    chapter_ids: list[int] = Field(default_factory=list)
    use_question_bank: bool | None = None  # 兼容旧前端：True 视为 bank

    @model_validator(mode="after")
    def validate_scope(self):
        if self.use_question_bank and self.question_source == QuestionSource.ai:
            self.question_source = QuestionSource.bank
        if self.source_type == HomeworkSourceType.courseware and not self.courseware_ids:
            raise ValueError("请选择关联课件")
        if self.source_type == HomeworkSourceType.textbook and not self.textbook_id:
            raise ValueError("请选择课本")
        if self.source_type == HomeworkSourceType.chapters:
            if not self.textbook_id:
                raise ValueError("请选择课本")
            if not self.chapter_ids:
                raise ValueError("请选择章节")
        return self


class HomeworkOut(BaseModel):
    id: int
    title: str
    paper_type: HomeworkType
    difficulty: DifficultyLevel
    gen_status: ParseStatus
    courseware_id: int | None
    courseware_ids: list | None = None
    textbook_id: int | None = None
    chapter_ids: list | None = None
    source_type: str | None = None
    question_source: str | None = None
    question_config: dict | None = None
    grade_id: int | None = None
    subject_id: int | None = None
    created_at: datetime
    creator_name: str | None = None
    is_owner: bool = False
    can_edit: bool = False
    can_manage_collab: bool = False
    model_config = {"from_attributes": True}


class HomeworkQuestionOut(BaseModel):
    id: int
    sort_order: int
    content: str
    options: dict | None = None
    answer: str | None = None
    question_type: str | None = None
    score: float | int | None = None
    source: str | None = None
    question_id: int | None = None
    model_config = {"from_attributes": True}


class HomeworkDetail(HomeworkOut):
    content: str | None
    questions: list[HomeworkQuestionOut] = []
