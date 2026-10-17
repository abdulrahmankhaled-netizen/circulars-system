"""
موديلات العقود.
"""
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Text, Float, Date, Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.core.mixins import TimestampMixin


class Contract(db.Model, TimestampMixin):
    """
    عقد مع مورد — يُنشأ يدوياً أو من طلب معتمد.
    """
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_number: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False, index=True
    )

    # ============ المورد ============
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    supplier = relationship("Supplier", backref="contracts")

        # ============ الجهة والمنطقة ============
    client_entity: Mapped[str] = mapped_column(String(150), nullable=True, index=True)
    client_entity_en: Mapped[str] = mapped_column(String(150), nullable=True)
    region: Mapped[str] = mapped_column(String(120), nullable=True, index=True)
    region_en: Mapped[str] = mapped_column(String(120), nullable=True)
    location_keywords: Mapped[str] = mapped_column(Text, nullable=True)

    # ============ المدد ============
    start_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=True)

    # ============ القيمة ============
    value: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="AED")
    value_period: Mapped[str] = mapped_column(String(20), default="per_mission")
    payment_terms: Mapped[str] = mapped_column(String(200), nullable=True)

    # ============ الحالة ============
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False, index=True
    )

    # ============ العقد الموقّع ============
    signed_document: Mapped[str] = mapped_column(String(255), nullable=True)
    signed_uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ============ سياق الإنشاء ============
    # إذا أُنشئ العقد من طلب معين
    source_request_id: Mapped[int] = mapped_column(Integer, nullable=True)

    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # ============ العلاقات ============
    equipment_items = relationship(
        "ContractEquipment",
        back_populates="contract",
        cascade="all, delete-orphan",
    )

    # ============ Helpers ============
    def display_name(self) -> str:
        return f"{self.contract_number} — {self.supplier.company_name_ar}"

    def days_to_expiry(self) -> int:
        if not self.end_date:
            return None
        return (self.end_date - datetime.utcnow().date()).days

    def value_period_label(self) -> str:
        labels = {
            "per_mission": "لكل مهمة",
            "monthly": "شهرياً",
            "quarterly": "كل 3 أشهر",
            "semi_annual": "كل 6 أشهر",
            "annual": "سنوياً",
        }
        return labels.get(self.value_period, "لكل مهمة")

    def __repr__(self):
        return f"<Contract {self.contract_number} ({self.status})>"


class ContractEquipment(db.Model):
    """معدة مشمولة بعقد + سعرها المتفق عليه."""
    __tablename__ = "contract_equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    contract = relationship("Contract", back_populates="equipment_items")

    equipment_key: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

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
        return f"<ContractEquip {self.equipment_key} x{self.quantity}>"