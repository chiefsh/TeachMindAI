from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import Optional
from urllib.parse import quote
import io

from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.homework import HomeworkPaper, HomeworkSourceType
from app.models.courseware import Courseware
from app.models.textbook import ParseStatus, Textbook
from app.schemas.homework import HomeworkCreate, HomeworkOut, HomeworkDetail
from app.api.deps import get_current_teacher
from app.services.export_service import build_homework_export

router = APIRouter(prefix="/homework", tags=["作业考试"])


@router.get("", response_model=list[HomeworkOut])
async def list_homework(
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = select(HomeworkPaper).where(HomeworkPaper.teacher_id == teacher.id)
    if grade_id or subject_id:
        tb_q = select(Textbook.id).where(Textbook.teacher_id == teacher.id)
        if grade_id:
            tb_q = tb_q.where(Textbook.grade_id == grade_id)
        if subject_id:
            tb_q = tb_q.where(Textbook.subject_id == subject_id)
        tb_ids = list((await db.execute(tb_q)).scalars().all())
        cw_ids = []
        if tb_ids:
            cw_ids = list((await db.execute(
                select(Courseware.id).where(
                    Courseware.teacher_id == teacher.id,
                    Courseware.textbook_id.in_(tb_ids),
                )
            )).scalars().all())
        q = q.where(or_(
            HomeworkPaper.textbook_id.in_(tb_ids or [-1]),
            HomeworkPaper.courseware_id.in_(cw_ids or [-1]),
        ))
    result = await db.execute(q.order_by(HomeworkPaper.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=HomeworkOut, status_code=201)
async def create_homework(
    data: HomeworkCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cfg = data.question_config or {}
    if not any(int(v or 0) > 0 for v in cfg.values()):
        raise HTTPException(status_code=400, detail="请至少配置一道题")

    cw_ids = list(data.courseware_ids or [])
    textbook_id = data.textbook_id
    chapter_ids = list(data.chapter_ids or [])
    if data.source_type != HomeworkSourceType.courseware:
        cw_ids = []
    if data.source_type == HomeworkSourceType.courseware:
        textbook_id = None
        chapter_ids = []
    if data.source_type != HomeworkSourceType.chapters:
        chapter_ids = []

    if cw_ids:
        rows = (await db.execute(
            select(Courseware).where(
                Courseware.id.in_(cw_ids),
                Courseware.teacher_id == teacher.id,
            )
        )).scalars().all()
        if len(rows) != len(set(cw_ids)):
            raise HTTPException(status_code=400, detail="课件不存在或无权使用")
        if any(r.gen_status != ParseStatus.done for r in rows):
            raise HTTPException(status_code=400, detail="请选择已生成完成的课件")
        if textbook_id is None:
            textbook_id = next((r.textbook_id for r in rows if r.textbook_id), None)

    if textbook_id:
        tb = (await db.execute(
            select(Textbook).where(
                Textbook.id == textbook_id, Textbook.teacher_id == teacher.id,
            )
        )).scalar_one_or_none()
        if not tb:
            raise HTTPException(status_code=400, detail="课本不存在或无权使用")

    paper = HomeworkPaper(
        teacher_id=teacher.id,
        courseware_id=cw_ids[0] if cw_ids else None,
        courseware_ids=cw_ids or None,
        textbook_id=textbook_id,
        chapter_ids=chapter_ids or None,
        source_type=data.source_type.value,
        question_source=data.question_source.value,
        title=data.title,
        paper_type=data.paper_type,
        difficulty=data.difficulty,
        question_config=data.question_config,
        gen_status=ParseStatus.pending,
    )
    db.add(paper)
    await db.flush()
    await db.refresh(paper)
    await db.commit()

    from app.tasks.ai_tasks import generate_homework_task
    task = generate_homework_task.delay(paper_id=paper.id)
    paper.task_id = task.id
    await db.commit()
    return paper


@router.get("/{paper_id}", response_model=HomeworkDetail)
async def get_homework(
    paper_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    return await _get_or_404(paper_id, teacher.id, db)


@router.get("/{paper_id}/export")
async def export_homework(
    paper_id: int,
    format: str = "docx",
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """导出作业/试卷为 docx / pdf"""
    fmt = (format or "docx").lower()
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="仅支持 docx / pdf")
    paper = await _get_or_404(paper_id, teacher.id, db)
    if paper.gen_status != ParseStatus.done:
        raise HTTPException(status_code=400, detail="作业尚未生成完成，无法导出")

    questions = [
        {"content": q.content, "options": q.options, "answer": q.answer, "score": q.score}
        for q in sorted(paper.questions, key=lambda x: x.sort_order)
    ]
    paper_type = getattr(paper.paper_type, "value", paper.paper_type)
    try:
        data, media_type, ext = build_homework_export(fmt, paper.title, str(paper_type), questions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{e}")

    filename = quote(f"{paper.title}.{ext}")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.delete("/{paper_id}", status_code=204)
async def delete_homework(
    paper_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    paper = await _get_or_404(paper_id, teacher.id, db)
    await db.delete(paper)


async def _get_or_404(paper_id: int, teacher_id: int, db: AsyncSession) -> HomeworkPaper:
    result = await db.execute(
        select(HomeworkPaper)
        .where(HomeworkPaper.id == paper_id, HomeworkPaper.teacher_id == teacher_id)
        .options(selectinload(HomeworkPaper.questions))
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="作业不存在")
    return paper
