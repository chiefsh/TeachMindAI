from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.teacher import Teacher
from app.models.student import Student, ExamResult, EntryMethod, GradeReport, ReportType
from app.models.teacher_setting import TeacherSetting
from app.models.textbook import ParseStatus
from app.schemas.student import (
    StudentCreate, StudentUpdate, StudentOut, ExamResultCreate, ExamResultOut, GradeStats,
    AnalysisCreate, AnalysisRegenerate, GradeReportOut, ExamSummaryOut, GradeLineConfig,
)
from app.api.deps import get_current_teacher

router = APIRouter(prefix="/students", tags=["学生成绩"])

# 高分线 / 低分线默认值（教师未设置时使用）
DEFAULT_HIGH_LINE = 85.0
DEFAULT_LOW_LINE = 60.0
GRADE_LINE_KEY = "grade_line"


async def _get_grade_lines(db: AsyncSession, teacher_id: int) -> tuple[float, float]:
    """读取教师的高/低分线配置，未设置则返回默认值。"""
    row = (await db.execute(
        select(TeacherSetting).where(
            TeacherSetting.teacher_id == teacher_id,
            TeacherSetting.key == GRADE_LINE_KEY,
        )
    )).scalar_one_or_none()
    val = row.value if row and isinstance(row.value, dict) else {}
    high = val.get("high_line", DEFAULT_HIGH_LINE)
    low = val.get("low_line", DEFAULT_LOW_LINE)
    return float(high), float(low)


@router.get("", response_model=list[StudentOut])
async def list_students(
    grade_id: Optional[int] = None,
    class_id: Optional[int] = None,
    class_name: Optional[str] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = select(Student).where(Student.teacher_id == teacher.id)
    if grade_id:
        q = q.where(Student.grade_id == grade_id)
    if class_id:
        q = q.where(Student.class_id == class_id)
    if class_name:
        q = q.where(Student.class_name == class_name)
    result = await db.execute(q.order_by(Student.class_name, Student.student_no))
    return result.scalars().all()


@router.post("", response_model=StudentOut, status_code=201)
async def create_student(
    data: StudentCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    from app.services import classroom_service as class_svc
    try:
        return await class_svc.add_student(
            db, teacher.id,
            student_no=data.student_no,
            name=data.name,
            grade_id=data.grade_id,
            class_id=data.class_id,
            class_name=data.class_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{student_id}", response_model=StudentOut)
async def update_student(
    student_id: int,
    data: StudentUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    from app.services import classroom_service as class_svc
    try:
        return await class_svc.update_student(db, teacher.id, student_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{student_id}", status_code=204)
async def delete_student(
    student_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    from app.services import classroom_service as class_svc
    try:
        await class_svc.delete_student(db, teacher.id, student_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ManualGradeRow(BaseModel):
    name: str = ""
    student_no: str = ""
    score: float | None = None


class ManualGradesIn(BaseModel):
    grade_id: int
    subject_id: int
    exam_name: str
    full_score: float = 100.0
    rows: list[ManualGradeRow]


@router.post("/manual-grades", status_code=201)
async def manual_grades(
    data: ManualGradesIn,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """手动批量录入成绩：按 姓名/学号/成绩 逐行录入，自动创建或复用学生。"""
    if not (data.exam_name or "").strip():
        raise HTTPException(status_code=400, detail="请填写考试名称")

    created = 0
    for row in data.rows:
        name = (row.name or "").strip()
        no = (row.student_no or "").strip()
        if row.score is None or (not name and not no):
            continue  # 跳过空行

        stu = None
        if no:
            res = await db.execute(
                select(Student).where(
                    Student.teacher_id == teacher.id,
                    Student.grade_id == data.grade_id,
                    Student.student_no == no,
                )
            )
            stu = res.scalar_one_or_none()
        if not stu:
            stu = Student(
                teacher_id=teacher.id,
                grade_id=data.grade_id,
                student_no=no or name,
                name=name or no,
            )
            db.add(stu)
            await db.flush()
        elif name and stu.name != name:
            stu.name = name

        db.add(ExamResult(
            teacher_id=teacher.id,
            student_id=stu.id,
            subject_id=data.subject_id,
            exam_name=data.exam_name.strip(),
            score=row.score,
            full_score=data.full_score,
            entry_method=EntryMethod.manual,
        ))
        created += 1

    if created == 0:
        raise HTTPException(status_code=400, detail="没有有效成绩行，请填写姓名/学号与成绩")
    return {"count": created}


@router.post("/batch-import", status_code=202)
async def import_students_from_file(
    file: UploadFile = File(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """从 Excel/Word 文档批量导入学生成绩"""
    data = await file.read()
    from app.tasks.file_tasks import import_grades_task
    task = import_grades_task.delay(teacher.id, file.filename, data)
    return {"task_id": task.id, "message": "文件已上传，正在解析"}


@router.post("/image-import", status_code=202)
async def import_grades_from_image(
    file: UploadFile = File(...),
    teacher: Teacher = Depends(get_current_teacher),
):
    """从图片 OCR 识别成绩"""
    data = await file.read()
    from app.tasks.ai_tasks import ocr_grades_task
    task = ocr_grades_task.delay(teacher.id, file.filename, data)
    return {"task_id": task.id, "message": "图片已上传，正在识别"}


# ─── 成绩录入 ─────────────────────────────────────────────────
@router.post("/results", response_model=list[ExamResultOut], status_code=201)
async def add_results(
    results: list[ExamResultCreate],
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    records = [ExamResult(teacher_id=teacher.id, **r.model_dump()) for r in results]
    db.add_all(records)
    await db.flush()
    for r in records:
        await db.refresh(r)
    return records


@router.get("/results", response_model=list[ExamResultOut])
async def list_results(
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    exam_name: Optional[str] = None,
    student_id: Optional[int] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(ExamResult, Student.name, Student.student_no, Student.grade_id)
        .join(Student, Student.id == ExamResult.student_id)
        .where(ExamResult.teacher_id == teacher.id)
    )
    if grade_id:
        q = q.where(Student.grade_id == grade_id)
    if subject_id:
        q = q.where(ExamResult.subject_id == subject_id)
    if exam_name:
        q = q.where(ExamResult.exam_name == exam_name)
    if student_id:
        q = q.where(ExamResult.student_id == student_id)
    rows = (await db.execute(q.order_by(ExamResult.created_at.desc()))).all()

    out = []
    for r, name, no, gid in rows:
        o = ExamResultOut.model_validate(r)
        o.student_name = name
        o.student_no = no
        o.grade_id = gid
        out.append(o)
    return out


@router.get("/grade-line-config", response_model=GradeLineConfig)
async def get_grade_line_config(
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取教师的高/低分线配置（未设置返回默认值）。"""
    high, low = await _get_grade_lines(db, teacher.id)
    return GradeLineConfig(high_line=high, low_line=low)


@router.put("/grade-line-config", response_model=GradeLineConfig)
async def save_grade_line_config(
    data: GradeLineConfig,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """保存教师的高/低分线配置。"""
    row = (await db.execute(
        select(TeacherSetting).where(
            TeacherSetting.teacher_id == teacher.id,
            TeacherSetting.key == GRADE_LINE_KEY,
        )
    )).scalar_one_or_none()
    payload = {"high_line": data.high_line, "low_line": data.low_line}
    if row:
        row.value = payload
    else:
        db.add(TeacherSetting(teacher_id=teacher.id, key=GRADE_LINE_KEY, value=payload))
    await db.flush()
    return data


@router.get("/results/summary", response_model=list[ExamSummaryOut])
async def summary_results(
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    high_line: Optional[float] = None,
    low_line: Optional[float] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """成绩概览：按「科目 + 考试名称」聚合，返回人数/最高/最低/平均/高分人数/低分人数。

    高分人数 = 得分 >= high_line；低分人数 = 得分 < low_line。
    high_line / low_line 未传时回退到教师配置（再无则默认值）。
    """
    cfg_high, cfg_low = await _get_grade_lines(db, teacher.id)
    high = high_line if high_line is not None else cfg_high
    low = low_line if low_line is not None else cfg_low

    # SQL 端聚合，避免成绩量大时全量拉入内存
    q = (
        select(
            Student.grade_id,
            ExamResult.subject_id,
            ExamResult.exam_name,
            func.count(ExamResult.id),
            func.max(ExamResult.score),
            func.min(ExamResult.score),
            func.avg(ExamResult.score),
            func.max(ExamResult.full_score),
            func.sum(case((ExamResult.score >= high, 1), else_=0)),
            func.sum(case((ExamResult.score < low, 1), else_=0)),
            func.max(ExamResult.created_at),
        )
        .join(Student, Student.id == ExamResult.student_id)
        .where(ExamResult.teacher_id == teacher.id)
        .group_by(Student.grade_id, ExamResult.subject_id, ExamResult.exam_name)
        .order_by(func.max(ExamResult.created_at).desc())
    )
    if grade_id:
        q = q.where(Student.grade_id == grade_id)
    if subject_id:
        q = q.where(ExamResult.subject_id == subject_id)

    rows = (await db.execute(q)).all()
    return [
        ExamSummaryOut(
            grade_id=gid, subject_id=sid, exam_name=ename,
            count=int(cnt or 0),
            max_score=float(mx or 0), min_score=float(mn or 0),
            avg_score=round(float(avg or 0), 2),
            full_score=float(full or 100),
            high_count=int(hi or 0), low_count=int(lo or 0),
            high_line=high, low_line=low, latest_at=latest,
        )
        for gid, sid, ename, cnt, mx, mn, avg, full, hi, lo, latest in rows
    ]


@router.get("/exam-names", response_model=list[str])
async def list_exam_names(
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取已有考试名称列表（用于下拉筛选），可按年级/科目过滤"""
    q = (
        select(ExamResult.exam_name)
        .join(Student, Student.id == ExamResult.student_id)
        .where(ExamResult.teacher_id == teacher.id)
    )
    if grade_id:
        q = q.where(Student.grade_id == grade_id)
    if subject_id:
        q = q.where(ExamResult.subject_id == subject_id)
    rows = (await db.execute(q.distinct())).scalars().all()
    return [r for r in rows if r]


async def _load_scores(db: AsyncSession, teacher_id: int, subject_id: int, exam_name: str) -> list[dict]:
    rows = (await db.execute(
        select(ExamResult, Student.name)
        .join(Student, Student.id == ExamResult.student_id)
        .where(
            ExamResult.teacher_id == teacher_id,
            ExamResult.subject_id == subject_id,
            ExamResult.exam_name == exam_name,
        )
    )).all()
    return [{"name": name, "score": r.score, "full_score": r.full_score} for r, name in rows]


async def _build_stats_content(db, teacher_id, subject_id, exam_name) -> dict:
    from app.services.grade_stats import compute_grade_stats
    scores = await _load_scores(db, teacher_id, subject_id, exam_name)
    stats = compute_grade_stats(scores)
    stats.update({"exam_name": exam_name, "subject_id": subject_id})
    return stats


async def _dispatch_ai(db, report: GradeReport):
    await db.commit()  # 确保 worker 能查到记录
    from app.tasks.ai_tasks import analyze_grades_task
    task = analyze_grades_task.delay(report.id)
    report.task_id = task.id
    report.gen_status = ParseStatus.processing
    await db.commit()


@router.post("/analysis", response_model=GradeReportOut, status_code=201)
async def create_analysis(
    data: AnalysisCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """创建成绩分析（统计分析同步完成；AI 报告异步生成）。"""
    count = (await db.execute(
        select(func.count()).select_from(ExamResult).where(
            ExamResult.teacher_id == teacher.id,
            ExamResult.subject_id == data.subject_id,
            ExamResult.exam_name == data.exam_name,
        )
    )).scalar()
    if not count:
        raise HTTPException(status_code=404, detail="未找到成绩数据")

    report = GradeReport(
        teacher_id=teacher.id,
        grade_id=data.grade_id,
        subject_id=data.subject_id,
        exam_name=data.exam_name,
        report_type=data.report_type,
        custom_prompt=data.custom_prompt,
    )

    if data.report_type == ReportType.stats:
        report.content = await _build_stats_content(db, teacher.id, data.subject_id, data.exam_name)
        report.gen_status = ParseStatus.done
        db.add(report)
        await db.flush()
        await db.refresh(report)
    else:
        report.gen_status = ParseStatus.pending
        db.add(report)
        await db.flush()
        await db.refresh(report)
        await _dispatch_ai(db, report)
    return report


@router.get("/analysis", response_model=list[GradeReportOut])
async def list_analysis(
    report_type: Optional[ReportType] = None,
    grade_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    q = select(GradeReport).where(GradeReport.teacher_id == teacher.id)
    if report_type:
        q = q.where(GradeReport.report_type == report_type)
    if grade_id:
        q = q.where(GradeReport.grade_id == grade_id)
    if subject_id:
        q = q.where(GradeReport.subject_id == subject_id)
    rows = (await db.execute(q.order_by(GradeReport.created_at.desc()))).scalars().all()
    return rows


@router.get("/analysis/{report_id}", response_model=GradeReportOut)
async def get_analysis(
    report_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    return await _get_report_or_404(report_id, teacher.id, db)


@router.delete("/analysis/{report_id}", status_code=204)
async def delete_analysis(
    report_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    report = await _get_report_or_404(report_id, teacher.id, db)
    await db.delete(report)


@router.post("/analysis/{report_id}/regenerate", response_model=GradeReportOut)
async def regenerate_analysis(
    report_id: int,
    data: AnalysisRegenerate,
    teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    report = await _get_report_or_404(report_id, teacher.id, db)
    if data.custom_prompt is not None:
        report.custom_prompt = data.custom_prompt

    if report.report_type == ReportType.stats:
        report.content = await _build_stats_content(db, teacher.id, report.subject_id, report.exam_name)
        report.gen_status = ParseStatus.done
        await db.flush()
        await db.refresh(report)
    else:
        report.content = None
        report.gen_status = ParseStatus.pending
        await db.flush()
        await _dispatch_ai(db, report)
        await db.refresh(report)
    return report


async def _get_report_or_404(report_id: int, teacher_id: int, db: AsyncSession) -> GradeReport:
    report = (await db.execute(
        select(GradeReport).where(GradeReport.id == report_id, GradeReport.teacher_id == teacher_id)
    )).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="分析报告不存在")
    return report
