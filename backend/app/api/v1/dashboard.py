from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.textbook import Textbook
from app.models.question import Question
from app.models.courseware import Courseware
from app.models.student import Student
from app.api.deps import get_current_teacher

router = APIRouter(prefix="/dashboard", tags=["工作台"])


async def _count(db: AsyncSession, model, teacher_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(model).where(model.teacher_id == teacher_id)
    )
    return result.scalar() or 0


@router.get("/stats")
async def get_dashboard_stats(
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """工作台统计：课本数、题目数、课件数、学生数"""
    return {
        "textbook_count": await _count(db, Textbook, teacher.id),
        "question_count": await _count(db, Question, teacher.id),
        "courseware_count": await _count(db, Courseware, teacher.id),
        "student_count": await _count(db, Student, teacher.id),
    }
