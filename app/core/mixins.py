"""
Mixins مشتركة لكل الموديلات.
"""
from datetime import datetime
from sqlalchemy import DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """يضيف created_at و updated_at تلقائياً."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SoftDeleteMixin:
    """حذف ناعم."""
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    deleted_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class CreatedByMixin:
    """يتتبع من أنشأ السجل."""
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )