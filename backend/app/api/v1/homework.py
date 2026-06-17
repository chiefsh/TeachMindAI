from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
from urllib.parse import quote
import io

from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.homework import HomeworkPaper
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
    # 试卷本身不直接挂年级/科目，按其关联课件所属课本进行过滤
    if grade_id or subject_id:
        q = (
            q.join(Courseware, Courseware.id == HomeworkPaper.courseware_id)
            .join(Textbook, Textbook.id == Courseware.textbook_id)
        )
        if grade_id:
            q = q.where(Textbook.grade_id == grade_id)
        if subject_id:
            q = q.where(Textbook.subject_id == subject_id)
    result = await db.execute(q.order_by(HomeworkPaper.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=HomeworkOut, status_code=201)
async def create_homework(
    data: HomeworkCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    paper = HomeworkPaper(
        teacher_id=teacher.id,
        courseware_id=data.courseware_ids[0] if data.courseware_ids else None,
        title=data.title,
        paper_type=data.paper_type,
        difficulty=data.difficulty,
        question_config=data.question_config,
        gen_status=ParseStatus.pending,
    )
    db.add(paper)
    await db.flush()
    await db.refresh(paper)
    # 先提交，确保 worker 能查到该行（避免 dispatch-before-commit 竞态）
    await db.commit()

    from app.tasks.ai_tasks import generate_homework_task
    task = generate_homework_task.delay(
        paper_id=paper.id,
        courseware_ids=data.courseware_ids,
        use_question_bank=data.use_question_bank,
    )
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
