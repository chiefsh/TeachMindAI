from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Teacher(Base, TimestampMixin):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    real_name: Mapped[str] = mapped_column(String(64), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    subjects = relationship("TeacherSubject", back_populates="teacher", cascade="all, delete-orphan")
    textbooks = relationship("Textbook", back_populates="teacher", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="teacher", cascade="all, delete-orphan")
    coursewares = relationship("Courseware", back_populates="teacher", cascade="all, delete-orphan")
    llm_configs = relationship("LLMConfig", back_populates="teacher", cascade="all, delete-orphan")
