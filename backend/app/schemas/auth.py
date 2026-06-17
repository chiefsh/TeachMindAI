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

    model_config = {"from_attributes": True}
