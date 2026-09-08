from pydantic import BaseModel, field_validator, Field
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


class CoursewareUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        t = (v or "").strip()
        if not t:
            raise ValueError("课件名称不能为空")
        return t[:256]


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


SLIDE_TYPES = (
    "cover", "objectives", "knowledge", "example", "interactive",
    "comparison", "process", "summary", "exercise", "homework",
    "title", "content", "intro", "activity", "board", "quiz",
)

OPTIMIZE_MODES = ("rewrite", "shorten", "expand", "examples", "notes", "interactive")


class SlidePatch(BaseModel):
    """人工按页保存：只改这些文本字段，不改 html / images / edit_status。"""
    type: str | None = None
    title: str | None = Field(None, max_length=200)
    subtitle: str | None = Field(None, max_length=300)
    bullets: list[str] | None = None
    content: str | None = None
    notes: str | None = None
    prompt: str | None = None
    solution: str | None = None
    left_title: str | None = Field(None, max_length=200)
    right_title: str | None = Field(None, max_length=200)

    @field_validator("title", "subtitle", "content", "notes", "prompt", "solution", "left_title", "right_title")
    @classmethod
    def _strip_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.strip()

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        t = v.strip()
        if t not in SLIDE_TYPES:
            raise ValueError("不支持的页面类型")
        return t

    @field_validator("bullets")
    @classmethod
    def _clean_bullets(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [str(x).strip() for x in v if str(x).strip()][:30]


class SlideInsert(BaseModel):
    index: int | None = Field(None, ge=0, description="插入位置（0 起），默认末尾")
    type: str = "knowledge"

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        t = (v or "knowledge").strip()
        if t not in SLIDE_TYPES:
            raise ValueError("不支持的页面类型")
        return t


class SlideReorder(BaseModel):
    order: list[int] = Field(..., min_length=1, description="当前下标的新排列")


class SlideOptimizeIn(BaseModel):
    instruction: str = Field("", max_length=2000)
    mode: str = "rewrite"

    @field_validator("instruction")
    @classmethod
    def _strip_instruction(cls, v: str) -> str:
        return (v or "").strip()[:2000]

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, v: str) -> str:
        m = (v or "rewrite").strip()
        if m not in OPTIMIZE_MODES:
            raise ValueError("不支持的优化方式")
        return m


class CoursewareExportIn(BaseModel):
    """PPT 导出时可附带互动页截图（slide 下标 → data URL / raw base64）。"""
    format: str = "pptx"
    shots: dict[str, str] | None = None
