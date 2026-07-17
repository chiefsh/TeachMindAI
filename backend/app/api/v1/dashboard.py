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


@router.get("/stats")
async def get_dashboard_stats(
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """工作台统计：课本数、题目数、课件数、学生数"""
    # 并行查询；同一 AsyncSession 不宜并发，改用一次多列聚合更安全
    row = (await db.execute(
        select(
            select(func.count()).select_from(Textbook).where(Textbook.teacher_id == teacher.id).scalar_subquery(),
            select(func.count()).select_from(Question).where(Question.teacher_id == teacher.id).scalar_subquery(),
            select(func.count()).select_from(Courseware).where(Courseware.teacher_id == teacher.id).scalar_subquery(),
            select(func.count()).select_from(Student).where(Student.teacher_id == teacher.id).scalar_subquery(),
        )
    )).one()
    return {
        "textbook_count": row[0] or 0,
        "question_count": row[1] or 0,
        "courseware_count": row[2] or 0,
        "student_count": row[3] or 0,
    }
