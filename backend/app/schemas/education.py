from pydantic import BaseModel


class SchoolLevelOut(BaseModel):
    id: int
    name: str
    sort_order: int
    model_config = {"from_attributes": True}


class GradeOut(BaseModel):
    id: int
    school_level_id: int
    name: str
    sort_order: int
    model_config = {"from_attributes": True}


class SubjectOut(BaseModel):
    id: int
    school_level_id: int
    name: str
    sort_order: int
    model_config = {"from_attributes": True}


class TeacherSubjectCreate(BaseModel):
    grade_id: int
    subject_id: int


class TeacherSubjectOut(BaseModel):
    id: int
    grade_id: int
    subject_id: int
    grade: GradeOut
    subject: SubjectOut
    model_config = {"from_attributes": True}
