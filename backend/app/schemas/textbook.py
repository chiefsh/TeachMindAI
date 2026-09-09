from pydantic import BaseModel
from datetime import datetime
from app.models.textbook import ParseStatus


class TextbookOut(BaseModel):
    id: int
    title: str
    file_name: str
    file_type: str
    file_size: int
    parse_status: ParseStatus
    total_pages: int | None
    subject_id: int
    grade_id: int
    created_at: datetime
    creator_name: str | None = None
    model_config = {"from_attributes": True}


class ChapterOut(BaseModel):
    id: int
    title: str
    level: int
    sort_order: int
    page_start: int | None
    page_end: int | None
    children: list["ChapterOut"] = []
    model_config = {"from_attributes": True}


ChapterOut.model_rebuild()


class TextbookCreate(BaseModel):
    title: str
    subject_id: int
    grade_id: int


class TextbookRelatedCounts(BaseModel):
    courseware: int = 0
    homework: int = 0
    questions: int = 0
