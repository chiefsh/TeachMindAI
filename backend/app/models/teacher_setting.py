from sqlalchemy import String, Integer, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class TeacherSetting(Base, TimestampMixin):
    """教师个性化设置（通用键值表，可复用于各类标量/小型配置）。

    例如成绩高/低分线：key='grade_line'，value={'high_line':85,'low_line':60}。
    """
    __tablename__ = "teacher_settings"
    __table_args__ = (UniqueConstraint("teacher_id", "key", name="uq_teacher_setting_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    teacher = relationship("Teacher")
