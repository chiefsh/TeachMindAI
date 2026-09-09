from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.education import SchoolLevel, Grade, Subject, TeacherSubject
from app.schemas.education import (
    SchoolLevelOut, GradeOut, SubjectOut,
    TeacherSubjectCreate, TeacherSubjectOut,
)
from app.api.deps import get_current_teacher, require_perm

router = APIRouter(prefix="/education", tags=["学段年级科目"])


@router.get("/school-levels", response_model=list[SchoolLevelOut])
async def get_school_levels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SchoolLevel).order_by(SchoolLevel.sort_order))
    return result.scalars().all()


@router.get("/grades", response_model=list[GradeOut])
async def get_grades(school_level_id: int | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Grade).order_by(Grade.school_level_id, Grade.sort_order)
    if school_level_id:
        q = q.where(Grade.school_level_id == school_level_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/subjects", response_model=list[SubjectOut])
async def get_subjects(school_level_id: int | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Subject).order_by(Subject.sort_order)
    if school_level_id:
        q = q.where(Subject.school_level_id == school_level_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/my-subjects", response_model=list[TeacherSubjectOut])
async def get_my_subjects(
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TeacherSubject)
        .options(selectinload(TeacherSubject.grade), selectinload(TeacherSubject.subject))
        .where(TeacherSubject.teacher_id == teacher.id)
    )
    return result.scalars().all()


@router.post("/my-subjects", response_model=TeacherSubjectOut, status_code=201)
async def add_my_subject(
    data: TeacherSubjectCreate,
    teacher: Teacher = Depends(require_perm("user.manage")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(TeacherSubject).where(
            TeacherSubject.teacher_id == teacher.id,
            TeacherSubject.grade_id == data.grade_id,
            TeacherSubject.subject_id == data.subject_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该年级科目已添加")

    ts = TeacherSubject(
        teacher_id=teacher.id,
        grade_id=data.grade_id,
        subject_id=data.subject_id,
    )
    db.add(ts)
    await db.flush()
    await db.refresh(ts, ["grade", "subject"])
    return ts


@router.delete("/my-subjects/{ts_id}", status_code=204)
async def remove_my_subject(
    ts_id: int,
    teacher: Teacher = Depends(require_perm("user.manage")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TeacherSubject).where(
            TeacherSubject.id == ts_id,
            TeacherSubject.teacher_id == teacher.id,
        )
    )
    ts = result.scalar_one_or_none()
    if not ts:
        raise HTTPException(status_code=404, detail="未找到")
    await db.delete(ts)
