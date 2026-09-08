"""知识图谱 API：知识点与关系的查询、维护，以及抽取/跨学科发现任务触发。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.models.teacher import Teacher
from app.models.education import Subject
from app.api.deps import get_current_teacher
from app.services import knowledge_graph_service as kg
from app.schemas.knowledge import (
    KnowledgePointCreate, RelationCreate, RelationOp, RelationStatusUpdate,
)

router = APIRouter(prefix="/knowledge", tags=["知识图谱"])


def _require_enabled():
    if not settings.KG_ENABLED:
        raise HTTPException(status_code=503, detail="知识图谱功能未启用")


@router.get("/graph")
async def get_graph(
    subject_id: Optional[int] = None,
    grade_id: Optional[int] = None,
    limit: int = 300,
    teacher: Teacher = Depends(get_current_teacher),
):
    _require_enabled()
    return await kg.get_graph(teacher.id, subject_id, grade_id, min(limit, 1000))


@router.get("/stats")
async def get_stats(teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    return await kg.stats(teacher.id)


@router.get("/points")
async def list_points(
    keyword: str = "",
    subject_id: Optional[int] = None,
    limit: int = 30,
    teacher: Teacher = Depends(get_current_teacher),
):
    _require_enabled()
    return await kg.search_points(teacher.id, keyword, subject_id, min(limit, 100))


@router.get("/points/{point_id}")
async def get_point(point_id: str, teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    node = await kg.get_point(point_id)
    if not node or node.get("teacher_id") != teacher.id:
        raise HTTPException(status_code=404, detail="知识点不存在")
    node["prerequisite_path"] = await kg.prerequisite_path(point_id)
    return node


@router.post("/points", status_code=201)
async def create_point(
    body: KnowledgePointCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    _require_enabled()
    subject_name, school_level_id = "", None
    if body.subject_id:
        sub = (await db.execute(select(Subject).where(Subject.id == body.subject_id))).scalar_one_or_none()
        if sub:
            subject_name, school_level_id = sub.name, sub.school_level_id
    from app.services.embedding_service import resolve_embedding
    gw = await resolve_embedding(db, teacher.id)
    res = await kg.upsert_knowledge_point(
        teacher_id=teacher.id, name=body.name, subject_id=body.subject_id,
        subject_name=subject_name, school_level_id=school_level_id,
        grade_id=body.grade_id, description=body.description,
        difficulty=body.difficulty, tags=body.tags, source="manual",
        embed_model=gw.model if gw else None,
        embed_api_base=gw.api_base if gw else None,
        embed_api_key=gw.api_key if gw else None,
    )
    if not res:
        raise HTTPException(status_code=400, detail="创建失败")
    return res


@router.delete("/points/{point_id}", status_code=204)
async def delete_point(point_id: str, teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    node = await kg.get_point(point_id)
    if not node or node.get("teacher_id") != teacher.id:
        raise HTTPException(status_code=404, detail="知识点不存在")
    await kg.delete_point(point_id)


@router.post("/relations", status_code=201)
async def create_relation(body: RelationCreate, teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    # 校验两端归属当前教师
    for pid in (body.from_id, body.to_id):
        node = await kg.get_point(pid)
        if not node or node.get("teacher_id") != teacher.id:
            raise HTTPException(status_code=404, detail="知识点不存在")
    try:
        ok = await kg.add_relation(
            from_id=body.from_id, to_id=body.to_id, rel_type=body.rel_type,
            weight=body.weight, cross_subject=body.cross_subject,
            status="approved", source="manual", evidence=body.evidence,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=400, detail="关系创建失败（起止相同？）")
    return {"ok": True}


@router.post("/relations/delete", status_code=204)
async def delete_relation(body: RelationOp, teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    await kg.delete_relation(body.from_id, body.to_id, body.rel_type)


@router.put("/relations/status")
async def update_relation_status(body: RelationStatusUpdate, teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    if body.status == "rejected":
        await kg.delete_relation(body.from_id, body.to_id, body.rel_type)
    else:
        await kg.set_relation_status(body.from_id, body.to_id, body.rel_type, body.status)
    return {"ok": True}


@router.post("/extract/chapter/{chapter_id}")
async def extract_chapter(chapter_id: int, teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    from app.tasks.knowledge_tasks import extract_chapter_task
    task = extract_chapter_task.delay(chapter_id, teacher.id)
    return {"task_id": task.id}


@router.post("/extract/textbook/{textbook_id}")
async def extract_textbook(textbook_id: int, teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    from app.tasks.knowledge_tasks import extract_textbook_task
    task = extract_textbook_task.delay(textbook_id, teacher.id)
    return {"task_id": task.id}


@router.post("/suggest-cross-subject")
async def suggest_cross_subject(teacher: Teacher = Depends(get_current_teacher)):
    _require_enabled()
    from app.tasks.knowledge_tasks import suggest_cross_subject_task
    task = suggest_cross_subject_task.delay(teacher.id)
    return {"task_id": task.id}
