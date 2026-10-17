"""
موديلات المستخدمين والأدوار.
"""
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.core.mixins import TimestampMixin


class Role(db.Model, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    label_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    permissions: Mapped[str] = mapped_column(Text, nullable=True)  # CSV
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # علاقات
    users = relationship("User", back_populates="role", lazy="dynamic")

    # ---------- Helpers ----------
    def get_permissions_list(self) -> list:
        if not self.permissions:
            return []
        return [p.strip() for p in self.permissions.split(",") if p.strip()]

    def set_permissions(self, perms: list):
        self.permissions = ",".join(perms)

    def __repr__(self):
        return f"<Role {self.name}>"


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )

    department: Mapped[str] = mapped_column(String(80), nullable=True)
    avatar: Mapped[str] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[str] = mapped_column(String(45), nullable=True)

    # علاقات
    role = relationship("Role", back_populates="users")

    # ---------- Password ----------
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # ---------- Properties ----------
    @property
    def is_admin(self) -> bool:
        return self.role and self.role.name == "admin"

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else ""

    @property
    def role_label(self) -> str:
        return self.role.label_ar if self.role else ""

    # ---------- Helpers ----------
    def has_role(self, *names) -> bool:
        return self.role and self.role.name in names

    def __repr__(self):
        return f"<User {self.username} ({self.role_name})>"