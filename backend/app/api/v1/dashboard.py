from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.textbook import Textbook
from app.models.question import Question
from app.models.courseware import Courseware
from app.models.student import Student
from app.models.question_analysis import AnalysisSet
from app.api.deps import get_current_teacher
from app.core.access import apply_org_scope, apply_private_scope

router = APIRouter(prefix="/dashboard", tags=["工作台"])


@router.get("/stats")
async def get_dashboard_stats(
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """工作台统计：共享资产全站计数，私有资源按可见范围计数"""
    tb_q = select(func.count()).select_from(Textbook)
    tb_q = await apply_org_scope(tb_q, Textbook.teacher_id, db, teacher)
    q_q = select(func.count()).select_from(Question)
    q_q = await apply_org_scope(q_q, Question.teacher_id, db, teacher)
    st_q = select(func.count()).select_from(Student)
    st_q = await apply_org_scope(st_q, Student.teacher_id, db, teacher)
    cw_q = select(func.count()).select_from(Courseware)
    cw_q = await apply_private_scope(cw_q, Courseware, db, teacher, "courseware")
    an_q = select(func.count()).select_from(AnalysisSet)
    an_q = await apply_private_scope(an_q, AnalysisSet, db, teacher, "analysis")
    row = (await db.execute(
        select(
            tb_q.scalar_subquery(),
            q_q.scalar_subquery(),
            cw_q.scalar_subquery(),
            st_q.scalar_subquery(),
            an_q.scalar_subquery(),
        )
    )).one()
    return {
        "textbook_count": row[0] or 0,
        "question_count": row[1] or 0,
        "courseware_count": row[2] or 0,
        "student_count": row[3] or 0,
        "analysis_count": row[4] or 0,
    }
