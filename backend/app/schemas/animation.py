from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class AnimationOut(BaseModel):
    id: int
    key: str
    title: str
    subject: str
    group: str
    kind: str
    origin: str
    teacher_id: int | None
    keywords: list[str] = []
    knowledge_tags: list[str] = []
    skill: str
    problem_type: str
    spec: dict = {}
    has_html: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}


class AnimationCreate(BaseModel):
    """从系统模板另存为我的动画。"""
    template_key: str = Field(..., min_length=1, max_length=80)
    title: str = Field(..., min_length=1, max_length=256)
    keywords: list[str] = []
    knowledge_tags: list[str] = []

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        t = (v or "").strip()
        if not t:
            raise ValueError("标题不能为空")
        return t[:256]

    @field_validator("keywords", "knowledge_tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out, seen = [], set()
        for x in v or []:
            t = str(x).strip()[:32]
            if t and t not in seen:
                seen.add(t)
                out.append(t)
            if len(out) >= 16:
                break
        return out


class AnimationUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=256)
    keywords: list[str] | None = None
    knowledge_tags: list[str] | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        t = v.strip()
        if not t:
            raise ValueError("标题不能为空")
        return t[:256]

    @field_validator("keywords", "knowledge_tags")
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return AnimationCreate._tags(v)
