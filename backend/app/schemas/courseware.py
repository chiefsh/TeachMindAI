from pydantic import BaseModel
from datetime import datetime
from app.models.textbook import ParseStatus
from app.models.courseware import CoursewareType


class CoursewareCreate(BaseModel):
    textbook_id: int | None = None
    title: str
    chapter_range: dict | None = None   # {"start_id": 1, "end_id": 5}
    page_range: dict | None = None      # {"start": 1, "end": 30}
    courseware_type: CoursewareType = CoursewareType.standard
    custom_prompt: str | None = None
    is_interactive: bool = False


class CoursewareOut(BaseModel):
    id: int
    title: str
    courseware_type: CoursewareType
    gen_status: ParseStatus
    is_interactive: bool
    textbook_id: int | None
    grade_id: int | None = None
    subject_id: int | None = None
    task_id: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class CoursewareDetail(CoursewareOut):
    content: dict | None
    custom_prompt: str | None
    chapter_range: dict | None
    page_range: dict | None
