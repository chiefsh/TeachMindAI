from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    teachers = relationship("Teacher", back_populates="organization")
    org_roles = relationship("OrgRole", back_populates="organization", cascade="all, delete-orphan")


class Permission(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    module: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("org_id", "code", name="uq_role_org_code"),
        Index("ix_roles_org_id", "org_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_super: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    organization = relationship("Organization")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_code", name="uq_role_perm"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_code: Mapped[str] = mapped_column(
        String(64), ForeignKey("permissions.code"), nullable=False,
    )

    role = relationship("Role", back_populates="permissions")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("teacher_id", "role_id", name="uq_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    teacher = relationship("Teacher", back_populates="user_roles")
    role = relationship("Role")


class OrgRole(Base):
    """历史表，产品已不再使用组织默认角色。"""
    __tablename__ = "org_roles"
    __table_args__ = (UniqueConstraint("org_id", "role_id", name="uq_org_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    organization = relationship("Organization", back_populates="org_roles")
    role = relationship("Role")


class TeacherAssignment(Base, TimestampMixin):
    """用户工作范围：年级 + 班级 + 科目，一对多。"""
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint(
            "teacher_id", "grade_id", "class_id", "subject_id",
            name="uq_teacher_assignment",
        ),
        Index("ix_teacher_assignments_teacher_id", "teacher_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id"), nullable=False)
    class_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("school_classes.id"), nullable=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)

    teacher = relationship("Teacher", back_populates="assignments")
    grade = relationship("Grade")
    school_class = relationship("SchoolClass")
    subject = relationship("Subject")


class ResourceCollaborator(Base, TimestampMixin):
    """私有资源协作者：courseware / homework / analysis / grading。"""
    __tablename__ = "resource_collaborators"
    __table_args__ = (
        UniqueConstraint("resource_type", "resource_id", "teacher_id", name="uq_resource_collab"),
        Index("ix_resource_collab_teacher", "teacher_id"),
        Index("ix_resource_collab_res", "resource_type", "resource_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=False)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    teacher = relationship("Teacher")
