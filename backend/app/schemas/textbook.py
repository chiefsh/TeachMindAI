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
