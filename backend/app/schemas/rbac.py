from pydantic import BaseModel, EmailStr, field_validator


class RoleBrief(BaseModel):
    id: int
    code: str
    name: str
    is_system: bool = False
    model_config = {"from_attributes": True}


class PermissionOut(BaseModel):
    code: str
    module: str
    name: str
    sort_order: int = 0
    model_config = {"from_attributes": True}


class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    is_system: bool
    is_super: bool
    permission_codes: list[str] = []
    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str
    permission_codes: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    permission_codes: list[str] | None = None


class AssignmentIn(BaseModel):
    grade_id: int
    subject_id: int
    class_id: int | None = None


class AssignmentOut(BaseModel):
    id: int
    grade_id: int
    subject_id: int
    class_id: int | None
    grade_name: str | None = None
    subject_name: str | None = None
    class_name: str | None = None
    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    real_name: str
    is_active: bool
    is_super: bool = False
    roles: list[RoleBrief] = []
    assignments: list[AssignmentOut] = []
    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    real_name: str
    password: str
    role_ids: list[int] = []
    assignments: list[AssignmentIn] = []

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少6位")
        return v


class UserUpdate(BaseModel):
    real_name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None
    role_ids: list[int] | None = None
    assignments: list[AssignmentIn] | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if len(v) < 6:
            raise ValueError("密码至少6位")
        return v


class ClassOptionOut(BaseModel):
    id: int
    grade_id: int
    name: str
    model_config = {"from_attributes": True}


class ColleagueOut(BaseModel):
    id: int
    username: str
    real_name: str


class CollaboratorOut(BaseModel):
    teacher_id: int
    real_name: str
    username: str
    can_edit: bool


class CollaboratorIn(BaseModel):
    teacher_id: int
    can_edit: bool = False


class BatchCollaboratorIn(BaseModel):
    resource_ids: list[int]
    items: list[CollaboratorIn] = []
    replace: bool = False

    @field_validator("resource_ids")
    @classmethod
    def resource_ids_limit(cls, v: list[int]) -> list[int]:
        ids = [i for i in dict.fromkeys(v) if i]
        if not ids:
            raise ValueError("请选择资源")
        if len(ids) > 50:
            raise ValueError("一次最多选择 50 项")
        return ids
