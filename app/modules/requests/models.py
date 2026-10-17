"""
موديلات طلبات المعدات (Equipment Requests).
"""
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Text, Boolean, Date,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.core.mixins import TimestampMixin


class EquipmentRequest(db.Model, TimestampMixin):
    """
    طلب معدة — يُنشأ من فريق النقل.
    يمر بمراحل workflow حتى يصبح "تم التعاقد".
    """
    __tablename__ = "equipment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_number: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True
    )

    # ============ الطالب ============
    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requester = relationship("User", foreign_keys=[requester_id])
    department: Mapped[str] = mapped_column(String(80), nullable=True)

    # ============ تفاصيل الطلب ============
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)

    # ============ الموقع والمدة ============
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    region: Mapped[str] = mapped_column(String(120), nullable=True)
    needed_from: Mapped[datetime] = mapped_column(Date, nullable=True)
    needed_until: Mapped[datetime] = mapped_column(Date, nullable=True)

    # ============ الجهة ============
    client_entity: Mapped[str] = mapped_column(String(150), nullable=True)

    # ============ الحالة (Workflow) ============
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False, index=True
    )

    # ============ المراجعة ============
    reviewed_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)

       # ============ العقد المرتبط (بعد التعاقد) ============
    # ملاحظة: سنستخدم Integer بدون ForeignKey مؤقتاً
    # حتى نبني وحدة العقود، ثم سنربطه لاحقاً
    matched_contract_id: Mapped[int] = mapped_column(
        Integer, nullable=True
    )
    contracted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ============ ملاحظات ============
    admin_notes: Mapped[str] = mapped_column(Text, nullable=True)

    # ============ العلاقات ============
    items = relationship(
        "EquipmentRequestItem",
        back_populates="request",
        cascade="all, delete-orphan",
    )

    # ============ Helpers ============
    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity or 0 for item in self.items)

    def priority_label(self) -> str:
        from app.core.constants import PRIORITIES
        from app.core.constants import get_label
        return get_label(PRIORITIES, self.priority)

    def priority_color(self) -> str:
        from app.core.constants import PRIORITIES
        from app.core.constants import get_color
        return get_color(PRIORITIES, self.priority)

    def days_duration(self) -> int:
        if not self.needed_from or not self.needed_until:
            return 0
        return (self.needed_until - self.needed_from).days + 1

    def __repr__(self):
        return f"<Request {self.request_number} ({self.status})>"


class EquipmentRequestItem(db.Model):
    """بند في الطلب — نوع معدة + كمية."""
    __tablename__ = "equipment_request_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("equipment_requests.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    request = relationship("EquipmentRequest", back_populates="items")

    equipment_key: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # ============ Helpers ============
    def equipment_name_ar(self) -> str:
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key:
                return eq["name_ar"]
        return self.equipment_key

    def equipment_name_en(self) -> str:
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key:
                return eq.get("name_en", self.equipment_key)
        return self.equipment_key

    def __repr__(self):
        return f"<Item {self.equipment_key} x{self.quantity}>"