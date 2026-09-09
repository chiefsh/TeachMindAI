"""班级与花名册：行政班全站公共；花名册跟班走。"""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import SchoolClass, Student


async def get_class(db: AsyncSession, class_id: int, teacher_id: int | None = None) -> SchoolClass | None:
    return (await db.execute(
        select(SchoolClass).where(SchoolClass.id == class_id)
    )).scalar_one_or_none()


async def _class_by_name(db: AsyncSession, grade_id: int, name: str, exclude_id: int | None = None) -> SchoolClass | None:
    q = select(SchoolClass).where(SchoolClass.grade_id == grade_id, SchoolClass.name == name)
    if exclude_id:
        q = q.where(SchoolClass.id != exclude_id)
    return (await db.execute(q)).scalar_one_or_none()


async def backfill_from_names(db: AsyncSession, teacher_id: int, grade_id: int | None = None):
    """把仅有 class_name、尚未挂 class_id 的学生收到已有公共班，没有则建班。"""
    q = select(Student.grade_id, Student.class_name).where(
        Student.teacher_id == teacher_id,
        Student.class_id.is_(None),
        Student.class_name.is_not(None),
        Student.class_name != "",
    )
    if grade_id:
        q = q.where(Student.grade_id == grade_id)
    pairs = {(g, n) for g, n in (await db.execute(q.distinct())).all() if n}
    if not pairs:
        return
    for gid, name in pairs:
        cls = await _class_by_name(db, gid, name[:32])
        if not cls:
            cls = SchoolClass(teacher_id=teacher_id, grade_id=gid, name=name[:32])
            db.add(cls)
            await db.flush()
        students = (await db.execute(
            select(Student).where(
                Student.teacher_id == teacher_id,
                Student.grade_id == gid,
                Student.class_name == name,
                Student.class_id.is_(None),
            )
        )).scalars().all()
        for s in students:
            s.class_id = cls.id


def _class_out(row: SchoolClass, student_count: int) -> dict:
    return {
        "id": row.id,
        "grade_id": row.grade_id,
        "name": row.name,
        "student_count": student_count,
        "created_at": row.created_at,
    }


async def list_classes(db: AsyncSession, teacher_id: int, grade_id: int | None = None) -> list[dict]:
    await backfill_from_names(db, teacher_id, grade_id)
    q = select(SchoolClass)
    if grade_id:
        q = q.where(SchoolClass.grade_id == grade_id)
    rows = list((await db.execute(q.order_by(SchoolClass.grade_id, SchoolClass.name))).scalars().all())
    counts = {}
    if rows:
        cnt_q = (
            select(Student.class_id, func.count(Student.id))
            .where(Student.class_id.in_([c.id for c in rows]))
            .group_by(Student.class_id)
        )
        counts = dict((await db.execute(cnt_q)).all())
    return [_class_out(c, int(counts.get(c.id, 0))) for c in rows]


async def create_class(db: AsyncSession, teacher_id: int, grade_id: int, name: str) -> SchoolClass:
    name = (name or "").strip()
    if not name:
        raise ValueError("请填写班级名称")
    name = name[:32]
    if await _class_by_name(db, grade_id, name):
        raise ValueError("该年级已有同名班级")
    row = SchoolClass(teacher_id=teacher_id, grade_id=grade_id, name=name)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def rename_class(db: AsyncSession, teacher_id: int, class_id: int, name: str) -> SchoolClass:
    row = await get_class(db, class_id)
    if not row:
        raise ValueError("班级不存在")
    name = (name or "").strip()[:32]
    if not name:
        raise ValueError("请填写班级名称")
    if await _class_by_name(db, row.grade_id, name, exclude_id=class_id):
        raise ValueError("该年级已有同名班级")
    row.name = name
    students = (await db.execute(
        select(Student).where(Student.class_id == class_id)
    )).scalars().all()
    for s in students:
        s.class_name = name
    await db.flush()
    return row


async def delete_class(db: AsyncSession, teacher_id: int, class_id: int):
    row = await get_class(db, class_id)
    if not row:
        raise ValueError("班级不存在")
    n = (await db.execute(
        select(func.count(Student.id)).where(Student.class_id == class_id)
    )).scalar() or 0
    if n:
        raise ValueError("请先把学生移出或删除后再删班级")
    await db.delete(row)


async def resolve_class(
    db: AsyncSession, teacher_id: int, class_id: int | None, class_name: str | None, grade_id: int,
) -> SchoolClass | None:
    if class_id:
        cls = await get_class(db, class_id)
        if not cls:
            raise ValueError("班级不存在")
        return cls
    name = (class_name or "").strip()
    if not name:
        return None
    cls = await _class_by_name(db, grade_id, name[:32])
    if cls:
        return cls
    return await create_class(db, teacher_id, grade_id, name)


async def find_student_by_no(
    db: AsyncSession, teacher_id: int, grade_id: int, student_no: str,
) -> Student | None:
    return (await db.execute(
        select(Student).where(
            Student.grade_id == grade_id,
            Student.student_no == student_no,
        )
    )).scalar_one_or_none()


def attach_class(stu: Student, cls: SchoolClass | None):
    if cls:
        stu.class_id = cls.id
        stu.class_name = cls.name
        stu.grade_id = cls.grade_id
    else:
        stu.class_id = None
        stu.class_name = None


async def add_student(
    db: AsyncSession, teacher_id: int, *,
    student_no: str, name: str, grade_id: int,
    class_id: int | None = None, class_name: str | None = None,
) -> Student:
    student_no = (student_no or "").strip()
    name = (name or "").strip()
    if not student_no or not name:
        raise ValueError("请填写学号和姓名")
    cls = await resolve_class(db, teacher_id, class_id, class_name, grade_id)
    if cls:
        grade_id = cls.grade_id
    hit = await find_student_by_no(db, teacher_id, grade_id, student_no)
    if hit:
        raise ValueError(f"学号 {student_no} 已存在")
    stu = Student(
        teacher_id=teacher_id,
        grade_id=grade_id,
        student_no=student_no[:32],
        name=name[:64],
    )
    attach_class(stu, cls)
    db.add(stu)
    await db.flush()
    await db.refresh(stu)
    return stu


async def update_student(
    db: AsyncSession, teacher_id: int, student_id: int, data,
) -> Student:
    stu = (await db.execute(
        select(Student).where(Student.id == student_id)
    )).scalar_one_or_none()
    if not stu:
        raise ValueError("学生不存在")
    if data.student_no is not None:
        no = data.student_no.strip()
        if not no:
            raise ValueError("学号不能为空")
        hit = await find_student_by_no(db, teacher_id, stu.grade_id, no)
        if hit and hit.id != stu.id:
            raise ValueError(f"学号 {no} 已存在")
        stu.student_no = no[:32]
    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise ValueError("姓名不能为空")
        stu.name = name[:64]
    if "class_id" in data.model_fields_set:
        if data.class_id:
            cls = await get_class(db, data.class_id)
            if not cls:
                raise ValueError("班级不存在")
            attach_class(stu, cls)
        else:
            attach_class(stu, None)
    return stu


async def delete_student(db: AsyncSession, teacher_id: int, student_id: int):
    stu = (await db.execute(
        select(Student).where(Student.id == student_id)
    )).scalar_one_or_none()
    if not stu:
        raise ValueError("学生不存在")
    await db.delete(stu)


async def batch_add_students(
    db: AsyncSession, teacher_id: int, class_id: int, rows: list,
) -> dict:
    cls = await get_class(db, class_id)
    if not cls:
        raise ValueError("班级不存在")
    created = 0
    skipped = 0
    for row in rows:
        no = (getattr(row, "student_no", None) or "").strip()
        name = (getattr(row, "name", None) or "").strip()
        if not no and not name:
            continue
        if not no:
            no = name
        if not name:
            name = no
        hit = await find_student_by_no(db, teacher_id, cls.grade_id, no)
        if hit:
            skipped += 1
            if hit.class_id != cls.id:
                attach_class(hit, cls)
            if name and hit.name != name:
                hit.name = name[:64]
            continue
        stu = Student(
            teacher_id=teacher_id,
            grade_id=cls.grade_id,
            student_no=no[:32],
            name=name[:64],
        )
        attach_class(stu, cls)
        db.add(stu)
        created += 1
    await db.flush()
    return {"created": created, "skipped": skipped}
