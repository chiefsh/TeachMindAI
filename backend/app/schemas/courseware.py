from pydantic import BaseModel, field_validator
from datetime import datetime
from app.models.textbook import ParseStatus
from app.models.courseware import CoursewareType, RenderStyle
from app.services.courseware_theme import DEFAULT_THEME, resolve_theme_key


class CoursewareCreate(BaseModel):
    textbook_id: int | None = None
    title: str
    chapter_range: dict | None = None   # 按章节：{"chapter_ids": [12, 15, 18]}
    page_range: dict | None = None      # 按页码：{"start": 1, "end": 30}
    courseware_type: CoursewareType = CoursewareType.standard
    render_style: RenderStyle = RenderStyle.ppt   # 呈现样式：幻灯片 / 网页
    theme: str = DEFAULT_THEME                    # 视觉主题 key
    custom_prompt: str | None = None
    is_interactive: bool = False

    @field_validator("theme")
    @classmethod
    def _known_theme(cls, v: str) -> str:
        return resolve_theme_key(v)


class CoursewareOut(BaseModel):
    id: int
    title: str
    courseware_type: CoursewareType
    render_style: RenderStyle
    theme: str
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
