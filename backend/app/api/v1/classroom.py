from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.models.teacher import Teacher
from app.api.deps import get_current_teacher
from app.schemas.student import ClassCreate, ClassUpdate, ClassOut, StudentOut, StudentCreate, StudentBatchIn
from app.services import classroom_service as svc

router = APIRouter(prefix="/classes", tags=["班级学生"])


def _err(e: ValueError, code: int = 400) -> HTTPException:
    msg = str(e)
    if "不存在" in msg:
        code = 404
    return HTTPException(status_code=code, detail=msg)


@router.get("", response_model=list[ClassOut])
async def list_classes(
    grade_id: Optional[int] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    return await svc.list_classes(db, teacher.id, grade_id)


@router.post("", response_model=ClassOut, status_code=201)
async def create_class(
    data: ClassCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.create_class(db, teacher.id, data.grade_id, data.name)
    except ValueError as e:
        raise _err(e)
    return {"id": row.id, "grade_id": row.grade_id, "name": row.name, "student_count": 0, "created_at": row.created_at}


@router.patch("/{class_id}", response_model=ClassOut)
async def rename_class(
    class_id: int,
    data: ClassUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.rename_class(db, teacher.id, class_id, data.name or "")
    except ValueError as e:
        raise _err(e)
    n = next((x["student_count"] for x in await svc.list_classes(db, teacher.id, row.grade_id) if x["id"] == class_id), 0)
    return svc._class_out(row, n)


@router.delete("/{class_id}", status_code=204)
async def delete_class(
    class_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc.delete_class(db, teacher.id, class_id)
    except ValueError as e:
        raise _err(e)


@router.get("/{class_id}/students", response_model=list[StudentOut])
async def list_class_students(
    class_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    cls = await svc.get_class(db, class_id, teacher.id)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    from sqlalchemy import select
    from app.models.student import Student
    rows = (await db.execute(
        select(Student).where(
            Student.teacher_id == teacher.id,
            Student.class_id == class_id,
        ).order_by(Student.student_no)
    )).scalars().all()
    return rows


@router.post("/{class_id}/students", response_model=StudentOut, status_code=201)
async def add_class_student(
    class_id: int,
    data: StudentCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.add_student(
            db, teacher.id,
            student_no=data.student_no,
            name=data.name,
            grade_id=data.grade_id,
            class_id=class_id,
        )
    except ValueError as e:
        raise _err(e)


@router.post("/{class_id}/students/batch")
async def batch_add_students(
    class_id: int,
    data: StudentBatchIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.batch_add_students(db, teacher.id, class_id, data.rows)
    except ValueError as e:
        raise _err(e)
