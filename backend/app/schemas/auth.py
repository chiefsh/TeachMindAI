from pydantic import BaseModel, EmailStr, field_validator


class TeacherRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    real_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少6位")
        return v


class PublicAuthConfig(BaseModel):
    enable_regist: bool


class TeacherLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    teacher_id: int
    real_name: str
    username: str


class TeacherProfile(BaseModel):
    id: int
    username: str
    email: str
    real_name: str
    avatar: str | None
    is_active: bool
    is_super: bool = False
    roles: list[dict] = []
    permissions: list[str] = []
    assignments: list[dict] = []

    model_config = {"from_attributes": True}


class TeacherProfileUpdate(BaseModel):
    real_name: str | None = None
    email: EmailStr | None = None

    @field_validator("real_name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        t = v.strip()
        if not t:
            raise ValueError("姓名不能为空")
        return t[:64]


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("新密码至少6位")
        return v
