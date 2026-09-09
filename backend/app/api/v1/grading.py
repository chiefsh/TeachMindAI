from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.models.teacher import Teacher
from app.api.deps import get_current_teacher, require_perm
from app.schemas.grading import (
    AssignmentCreate, AssignmentOut, AssignmentDetail, SubmissionDetail,
    AnswerBatchIn, PageOrderIn, WrongItemOut,
    CollectMetaOut, CollectUploadOut, CollectTokenOut,
)
from app.models.grading import PaperSubmission
from app.services import grading_service as svc

router = APIRouter(prefix="/grading", tags=["批改作业试卷"])
public_router = APIRouter(prefix="/public/grading", tags=["批改公开收集"])


def _err(e: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


@router.post("/assignments", response_model=AssignmentOut, status_code=201)
async def create_assignment(
    data: AssignmentCreate,
    teacher: Teacher = Depends(require_perm("grading.create")),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.create_assignment(db, teacher.id, data)
    except ValueError as e:
        raise _err(e)
    roster = await svc._roster(db, row)
    return svc._assignment_out(row, len(roster))


@router.get("/assignments", response_model=list[AssignmentOut])
async def list_assignments(
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    class_name: Optional[str] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    return await svc.list_assignments(db, teacher.id, grade_id, subject_id, class_name)


@router.get("/assignments/{assignment_id}", response_model=AssignmentDetail)
async def get_assignment(
    assignment_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.get_assignment_detail(db, assignment_id, teacher.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment_id: int,
    teacher: Teacher = Depends(require_perm("grading.edit")),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc.delete_assignment(db, assignment_id, teacher.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await db.commit()


@router.get("/assignments/{assignment_id}/students/{student_id}", response_model=SubmissionDetail)
async def get_student_submission(
    assignment_id: int,
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await svc.submission_detail(db, assignment_id, student_id, teacher.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return data


@router.post("/submissions/{submission_id}/pages", response_model=SubmissionDetail)
async def upload_pages(
    submission_id: int,
    files: list[UploadFile] = File(...),
    teacher: Teacher = Depends(require_perm("grading.edit")),
    db: AsyncSession = Depends(get_db),
):
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        payloads.append((f.filename or "page.jpg", await f.read()))
    if not payloads:
        raise HTTPException(status_code=400, detail="请选择图片或 PDF")
    try:
        sub = await svc.add_pages(db, submission_id, teacher.id, payloads)
        data = await svc.submission_detail(db, sub.assignment_id, sub.student_id, teacher.id)
    except ValueError as e:
        raise _err(e)
    await db.commit()
    return data


@router.delete("/submissions/{submission_id}/pages/{page_id}", response_model=SubmissionDetail)
async def delete_page(
    submission_id: int,
    page_id: int,
    teacher: Teacher = Depends(require_perm("grading.edit")),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc.delete_page(db, submission_id, page_id, teacher.id)
        sub = await db.get(PaperSubmission, submission_id)
        if not sub:
            raise ValueError("答卷不存在")
        data = await svc.submission_detail(db, sub.assignment_id, sub.student_id, teacher.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return data


@router.put("/submissions/{submission_id}/pages/order", status_code=204)
async def reorder_pages(
    submission_id: int,
    data: PageOrderIn,
    teacher: Teacher = Depends(require_perm("grading.edit")),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc.reorder_pages(db, submission_id, teacher.id, data.page_ids)
    except ValueError as e:
        raise _err(e)
    await db.commit()


@router.put("/submissions/{submission_id}/answers", response_model=SubmissionDetail)
async def grade_answers(
    submission_id: int,
    data: AnswerBatchIn,
    teacher: Teacher = Depends(require_perm("grading.edit")),
    db: AsyncSession = Depends(get_db),
):
    try:
        sub = await svc.grade_answers(db, submission_id, teacher.id, data.items)
        detail = await svc.submission_detail(db, sub.assignment_id, sub.student_id, teacher.id)
    except ValueError as e:
        raise _err(e)
    await db.commit()
    return detail


@router.get("/wrong-questions", response_model=list[WrongItemOut])
async def list_wrong_questions(
    scope: str = "student",
    assignment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    if scope not in ("student", "assignment", "bank"):
        raise HTTPException(status_code=400, detail="scope 须为 student / assignment / bank")
    return await svc.list_wrong_questions(
        db, teacher.id, scope, assignment_id, student_id, grade_id, subject_id,
    )


@router.post("/assignments/{assignment_id}/collect-token", response_model=CollectTokenOut)
async def ensure_collect_token(
    assignment_id: int,
    teacher: Teacher = Depends(require_perm("grading.edit")),
    db: AsyncSession = Depends(get_db),
):
    try:
        token = await svc.ensure_collect_token(db, assignment_id, teacher.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return CollectTokenOut(token=token)


@public_router.get("/{token}", response_model=CollectMetaOut)
async def public_collect_meta(token: str, db: AsyncSession = Depends(get_db)):
    try:
        return await svc.collect_meta(db, token)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@public_router.post("/{token}/pages", response_model=CollectUploadOut)
async def public_collect_pages(
    token: str,
    student_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        payloads.append((f.filename or "page.jpg", await f.read()))
    if not payloads:
        raise HTTPException(status_code=400, detail="请选择图片")
    try:
        data = await svc.collect_upload_pages(db, token, student_id, payloads)
    except ValueError as e:
        msg = str(e)
        code = 404 if "链接" in msg or "不存在" in msg else 400
        raise HTTPException(status_code=code, detail=msg)
    await db.commit()
    return data
