from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ShareResourceType = Literal["courseware", "courseware_version", "question_analysis"]


class ShareCreateIn(BaseModel):
    resource_type: ShareResourceType
    resource_id: int
    expire_days: int | None = 5
    password: str | None = None

    @field_validator("expire_days", mode="before")
    @classmethod
    def _days(cls, v):
        if v is None or v == "":
            return 5
        try:
            n = int(v)
        except (TypeError, ValueError):
            return 5
        if n < 1 or n > 90:
            raise ValueError("过期天数须在 1～90 天之间")
        return n

    @field_validator("password", mode="before")
    @classmethod
    def _pwd(cls, v):
        s = str(v or "").strip()
        if not s:
            return None
        if len(s) < 4 or len(s) > 64:
            raise ValueError("密码长度须为 4～64 位")
        return s


class ShareOut(BaseModel):
    id: int
    token: str
    resource_type: str
    resource_id: int
    title: str = ""
    has_password: bool = False
    expires_at: datetime
    revoked: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}


class ShareAccessIn(BaseModel):
    password: str | None = Field(default=None, max_length=64)


class ShareMetaOut(BaseModel):
    status: Literal["ok", "need_password", "expired", "revoked", "not_found"]
    title: str = ""
    resource_type: str | None = None
    has_password: bool = False
    expires_at: datetime | None = None


class SharePayloadOut(BaseModel):
    resource_type: str
    title: str
    expires_at: datetime
    payload: dict[str, Any]
