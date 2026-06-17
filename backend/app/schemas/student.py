from pydantic import BaseModel
from datetime import datetime
from app.models.student import EntryMethod, ReportType
from app.models.textbook import ParseStatus


class StudentCreate(BaseModel):
    student_no: str
    name: str
    grade_id: int
    class_name: str | None = None


class StudentOut(BaseModel):
    id: int
    student_no: str
    name: str
    grade_id: int
    class_name: str | None
    model_config = {"from_attributes": True}


class ExamResultCreate(BaseModel):
    student_id: int
    subject_id: int
    exam_name: str
    score: float
    full_score: float = 100.0
    entry_method: EntryMethod = EntryMethod.manual
    remark: str | None = None


class ExamResultOut(BaseModel):
    id: int
    student_id: int
    subject_id: int
    exam_name: str
    score: float
    full_score: float
    entry_method: EntryMethod
    created_at: datetime
    student_name: str | None = None
    student_no: str | None = None
    grade_id: int | None = None
    model_config = {"from_attributes": True}


class GradeStats(BaseModel):
    exam_name: str
    subject_id: int
    avg_score: float
    max_score: float
    min_score: float
    pass_rate: float        # 及格率
    excellent_rate: float   # 优秀率
    score_distribution: dict  # {"[90,100]":5,"[80,90]":10,...}


class AnalysisCreate(BaseModel):
    grade_id: int | None = None
    subject_id: int
    exam_name: str
    report_type: ReportType
    custom_prompt: str | None = None


class AnalysisRegenerate(BaseModel):
    custom_prompt: str | None = None


class GradeReportOut(BaseModel):
    id: int
    grade_id: int | None
    subject_id: int
    exam_name: str
    report_type: ReportType
    custom_prompt: str | None
    content: dict | None
    gen_status: ParseStatus
    created_at: datetime
    model_config = {"from_attributes": True}
