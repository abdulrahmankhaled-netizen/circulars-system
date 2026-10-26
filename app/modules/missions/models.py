"""
موديلات المهام (Towing Missions).
"""
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Text, Float, Boolean, Date,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.core.mixins import TimestampMixin


class Mission(db.Model, TimestampMixin):
    """مهمة سحب/نقل مرتبطة بعقد."""
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_number: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True
    )

    # العلاقات
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    contract = relationship("Contract", backref="missions")

    request_id: Mapped[int] = mapped_column(
        ForeignKey("equipment_requests.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    request = relationship("EquipmentRequest", backref="missions")

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by = relationship("User", foreign_keys=[created_by_id])

    # المعدة
    equipment_key: Mapped[str] = mapped_column(String(80), nullable=False)

    # العميل
    customer_name: Mapped[str] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(40), nullable=True)

    # المركبة
    vehicle_plate: Mapped[str] = mapped_column(String(40), nullable=True)
    vehicle_make: Mapped[str] = mapped_column(String(80), nullable=True)
    vehicle_model: Mapped[str] = mapped_column(String(80), nullable=True)
    vehicle_vin: Mapped[str] = mapped_column(String(80), nullable=True)

    # الموقع
    pickup_location: Mapped[str] = mapped_column(String(255), nullable=True)
    drop_location: Mapped[str] = mapped_column(String(255), nullable=True)
    region: Mapped[str] = mapped_column(String(120), nullable=True)

    # التواريخ
    mission_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # السائق
    driver_name: Mapped[str] = mapped_column(String(120), nullable=True)
    driver_phone: Mapped[str] = mapped_column(String(40), nullable=True)

    # الحالة
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False, index=True
    )

    # حقول الشبك
    is_impound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    store_number: Mapped[str] = mapped_column(String(80), nullable=True, index=True)
    job_order_id: Mapped[str] = mapped_column(String(80), nullable=True, index=True)

    # حقول Excel
    qr_code: Mapped[str] = mapped_column(Text, nullable=True)
    job_id_external: Mapped[str] = mapped_column(String(80), nullable=True, index=True)
    payer_type: Mapped[str] = mapped_column(String(50), nullable=True)
    requested_rec_type: Mapped[str] = mapped_column(String(120), nullable=True)
    actual_rec_type: Mapped[str] = mapped_column(String(120), nullable=True)
    job_status: Mapped[str] = mapped_column(String(50), nullable=True)
    sub_status: Mapped[str] = mapped_column(String(80), nullable=True)
    advisor: Mapped[str] = mapped_column(String(120), nullable=True)
    service_centre: Mapped[str] = mapped_column(String(150), nullable=True)
    toll_job_id: Mapped[str] = mapped_column(String(80), nullable=True)
    toll_amount: Mapped[float] = mapped_column(Float, nullable=True)

    created_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    started_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # المالية
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, default=0.0)

    supplier_payment_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )
    customer_invoice_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )
    
    # ⭐ جديد: متابعة الدفع
    followup_status: Mapped[str] = mapped_column(String(30), default="pending")
    payment_notes: Mapped[str] = mapped_column(Text, nullable=True)

    notes: Mapped[str] = mapped_column(Text, nullable=True)
    completion_notes: Mapped[str] = mapped_column(Text, nullable=True)

    assigned_to_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    verified_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_by = relationship("User", foreign_keys=[verified_by_id])
    verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Helpers
    def equipment_name_ar(self) -> str:
        try:
            from app.modules.equipment.models import EquipmentType
            eq = EquipmentType.query.filter_by(key=self.equipment_key).first()
            if eq and eq.name_ar:
                return eq.name_ar
        except Exception:
            pass
            
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key:
                return eq["name_ar"]
        return self.equipment_key

    def equipment_name_en(self) -> str:
        try:
            from app.modules.equipment.models import EquipmentType
            eq = EquipmentType.query.filter_by(key=self.equipment_key).first()
            if eq and eq.name_en:
                return eq.name_en
        except Exception:
            pass
            
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key:
                return eq.get("name_en", self.equipment_key)
        return self.equipment_key

    def equipment_name_en(self) -> str:
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key:
                return eq.get("name_en", self.equipment_key)
        return self.equipment_key

    def recalculate_financials(self):
        self.profit = (self.revenue or 0) - (self.cost or 0)

    def duration_minutes(self):
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() / 60)
        return None

    def duration_label(self):
        m = self.duration_minutes()
        if not m:
            return "—"
        if m < 60:
            return f"{m} دقيقة"
        h = m // 60
        rm = m % 60
        return f"{h}س {rm}د"

    def supplier_payment_label(self) -> str:
        labels = {"pending": "معلّق", "paid": "مدفوع", "cancelled": "ملغي"}
        return labels.get(self.supplier_payment_status, "—")

    def supplier_payment_color(self) -> str:
        colors = {"pending": "warning", "paid": "success", "cancelled": "secondary"}
        return colors.get(self.supplier_payment_status, "secondary")

    def customer_invoice_label(self) -> str:
        labels = {
            "pending": "بانتظار الفاتورة",
            "invoiced": "مفوتر",
            "paid": "مدفوع",
            "cancelled": "ملغي",
        }
        return labels.get(self.customer_invoice_status, "—")

    def customer_invoice_color(self) -> str:
        colors = {
            "pending": "warning",
            "invoiced": "info",
            "paid": "success",
            "cancelled": "secondary",
        }
        return colors.get(self.customer_invoice_status, "secondary")

    def __repr__(self):
        return f"<Mission {self.mission_number} ({self.status})>"