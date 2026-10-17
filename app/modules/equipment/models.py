"""
موديلات المعدات والأسعار.
"""
from datetime import datetime
from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Text, Float, Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.core.mixins import TimestampMixin


class EquipmentPrice(db.Model, TimestampMixin):
    """
    سعر معدة عند مورد معين.
    """
    __tablename__ = "equipment_prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    # العلاقات
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    supplier = relationship("Supplier", backref="equipment_prices")

    # نوع المعدة
    equipment_key: Mapped[str] = mapped_column(
        String(80), nullable=False, index=True
    )

    # التسعير
    unit_price: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="AED", nullable=False
    )

    # تفاصيل
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    # Helpers
    def equipment_name_ar(self) -> str:
        """الاسم العربي من EquipmentType أو من constants."""
        try:
            t = EquipmentType.query.filter_by(key=self.equipment_key).first()
            if t:
                return t.name_ar
        except Exception:
            pass
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key:
                return eq["name_ar"]
        return self.equipment_key

    def equipment_name_en(self) -> str:
        try:
            t = EquipmentType.query.filter_by(key=self.equipment_key).first()
            if t and t.name_en:
                return t.name_en
        except Exception:
            pass
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key:
                return eq.get("name_en", self.equipment_key)
        return self.equipment_key

    def __repr__(self):
        return f"<EquipmentPrice {self.supplier_id}/{self.equipment_key}={self.unit_price}>"


class EquipmentType(db.Model):
    """
    نوع معدة قابل للإدارة من الواجهة.
    """
    __tablename__ = "equipment_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False, index=True
    )
    name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<EquipmentType {self.key} — {self.name_ar}>"