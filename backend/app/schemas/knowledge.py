"""知识图谱相关的请求/响应 schema。"""
from pydantic import BaseModel, Field
from typing import Optional


class KnowledgePointCreate(BaseModel):
    name: str
    subject_id: Optional[int] = None
    grade_id: Optional[int] = None
    description: str = ""
    difficulty: int = 3
    tags: list[str] = Field(default_factory=list)


class RelationCreate(BaseModel):
    from_id: str
    to_id: str
    rel_type: str = "related"          # prerequisite/part_of/related/application/contrast
    weight: float = 0.6
    cross_subject: bool = False
    evidence: str = ""


class RelationOp(BaseModel):
    from_id: str
    to_id: str
    rel_type: str


class RelationStatusUpdate(BaseModel):
    from_id: str
    to_id: str
    rel_type: str
    status: str                        # approved / rejected
