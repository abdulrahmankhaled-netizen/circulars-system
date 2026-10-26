"""
موديلات العقود.
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Float, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db
from app.core.mixins import TimestampMixin


class Contract(db.Model, TimestampMixin):
    """
    عقد مع مورد — يُنشأ يدوياً أو من طلب معتمد.
    """
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True)
    supplier = relationship("Supplier", backref="contracts")

    # ============ الجهة والمنطقة ============
    client_entity: Mapped[str] = mapped_column(String(150), nullable=True, index=True)
    client_entity_en: Mapped[str] = mapped_column(String(150), nullable=True)
    region: Mapped[str] = mapped_column(String(120), nullable=True, index=True)
    region_en: Mapped[str] = mapped_column(String(120), nullable=True)
    location_keywords: Mapped[str] = mapped_column(Text, nullable=True)
    project_name: Mapped[str] = mapped_column(String(150), nullable=True, index=True)

    # ============ المدد ============
    start_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=True)

    # ============ القيمة ============
    value: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="AED")
    value_period: Mapped[str] = mapped_column(String(20), default="per_mission")
    payment_terms: Mapped[str] = mapped_column(String(200), nullable=True)

    # ============ شروط الاتفاقية الإطارية ============
    term_duration: Mapped[str] = mapped_column(String(50), default="سنة واحدة")
    response_time_dubai: Mapped[int] = mapped_column(Integer, default=30)
    response_time_other: Mapped[int] = mapped_column(Integer, default=60)
    notice_days: Mapped[int] = mapped_column(Integer, default=30)
    payment_days: Mapped[int] = mapped_column(Integer, default=30)
    penalty_late: Mapped[float] = mapped_column(Float, default=100.0)
    penalty_late_mins: Mapped[int] = mapped_column(Integer, default=30)
    penalty_noshow: Mapped[float] = mapped_column(Float, default=500.0)
    penalty_unlisted: Mapped[float] = mapped_column(Float, default=500.0)
    penalty_article5: Mapped[float] = mapped_column(Float, default=5000.0)
    penalty_docs: Mapped[float] = mapped_column(Float, default=100.0)
    penalty_max_percent: Mapped[int] = mapped_column(Integer, default=20)
    penalty_max_times: Mapped[int] = mapped_column(Integer, default=3)
    penalty_max_months: Mapped[int] = mapped_column(Integer, default=6)
    insurance_liability_aed: Mapped[float] = mapped_column(Float, default=1000000.0)
    insurance_goods_aed: Mapped[float] = mapped_column(Float, default=500000.0)
    compensation_days: Mapped[int] = mapped_column(Integer, default=7)
    incident_report_hours: Mapped[int] = mapped_column(Integer, default=24)
    invoice_submit_days: Mapped[int] = mapped_column(Integer, default=5)
    invoice_review_days: Mapped[int] = mapped_column(Integer, default=7)
    cure_days: Mapped[int] = mapped_column(Integer, default=15)
    handover_hours: Mapped[int] = mapped_column(Integer, default=24)
    liability_months: Mapped[int] = mapped_column(Integer, default=6)
    confidentiality_years: Mapped[int] = mapped_column(Integer, default=5)
    force_majeure_hours: Mapped[int] = mapped_column(Integer, default=48)
    equipment_age_years: Mapped[int] = mapped_column(Integer, default=5)
    doc_upload_hours: Mapped[int] = mapped_column(Integer, default=2)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=14)
    company_coordinator: Mapped[str] = mapped_column(String(100), nullable=True)
    company_phone: Mapped[str] = mapped_column(String(50), nullable=True)
    company_email: Mapped[str] = mapped_column(String(100), nullable=True)

    # ============ الحالة ============
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)
    signed_document: Mapped[str] = mapped_column(String(255), nullable=True)
    signed_uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    source_request_id: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # ============ العلاقات ============
    equipment_items = relationship("ContractEquipment", back_populates="contract", cascade="all, delete-orphan")

    # ============ Helpers ============
    def display_name(self) -> str:
        return f"{self.contract_number} — {self.supplier.company_name_ar}"

    def days_to_expiry(self) -> int:
        if not self.end_date: return None
        return (self.end_date - datetime.utcnow().date()).days

    def value_period_label(self) -> str:
        labels = {"per_mission": "لكل مهمة", "monthly": "شهرياً", "quarterly": "كل 3 أشهر", "semi_annual": "كل 6 أشهر", "annual": "سنوياً", "mixed": "متنوع"}
        if self.equipment_items:
            periods = set(item.pricing_period for item in self.equipment_items if item.pricing_period)
            if len(periods) == 1: return labels.get(list(periods)[0], "لكل مهمة")
            elif len(periods) > 1: return labels.get("mixed", "متنوع")
        return labels.get(self.value_period, "لكل مهمة")

    @property
    def calculated_value(self) -> float:
        # ⭐ يجمع فقط التكاليف الثابتة (شهري/سنوي) ولا يجمع (لكل مهمة)
        if self.equipment_items:
            total_fixed = 0.0
            for item in self.equipment_items:
                if item.pricing_period and item.pricing_period != 'per_mission':
                    total_fixed += (item.quantity or 1) * (item.unit_price or 0)
            if total_fixed > 0:
                return total_fixed
        return self.value or 0.0

    @property
    def duration_text(self):
        if not self.start_date or not self.end_date: return self.term_duration or "غير محدد"
        delta = self.end_date - self.start_date
        days = delta.days
        if days <= 0: return "غير محدد"
        years = days // 365
        months = (days % 365) // 30
        remaining_days = (days % 365) % 30
        parts = []
        if years > 0: parts.append(f"{years} سنة")
        if months > 0: parts.append(f"{months} شهر")
        if remaining_days > 0 and years == 0: parts.append(f"{remaining_days} يوم")
        return " و ".join(parts) if parts else "أقل من شهر"

    @property
    def duration_text_en(self):
        if not self.start_date or not self.end_date: return self.term_duration or "Not specified"
        delta = self.end_date - self.start_date
        days = delta.days
        if days <= 0: return "Not specified"
        years = days // 365
        months = (days % 365) // 30
        remaining_days = (days % 365) % 30
        parts = []
        if years > 0: parts.append(f"{years} Year{'s' if years > 1 else ''}")
        if months > 0: parts.append(f"{months} Month{'s' if months > 1 else ''}")
        if remaining_days > 0 and years == 0: parts.append(f"{remaining_days} Day{'s' if remaining_days > 1 else ''}")
        return " and ".join(parts) if parts else "Less than a month"


class ContractEquipment(db.Model):
    """
    معدة مشمولة بعقد + سعرها المتفق عليه.
    """
    __tablename__ = "contract_equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    contract = relationship("Contract", back_populates="equipment_items")

    equipment_key: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    pricing_period: Mapped[str] = mapped_column(String(30), default="per_mission")
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def equipment_name_ar(self) -> str:
        try:
            from app.modules.equipment.models import EquipmentType
            t = EquipmentType.query.filter_by(key=self.equipment_key).first()
            if t and t.name_ar: return t.name_ar
        except Exception: pass
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key: return eq.get("name_ar", self.equipment_key)
        return self.equipment_key

    def equipment_name_en(self) -> str:
        try:
            from app.modules.equipment.models import EquipmentType
            t = EquipmentType.query.filter_by(key=self.equipment_key).first()
            if t and t.name_en: return t.name_en
        except Exception: pass
        from app.core.constants import EQUIPMENT_TYPES
        for eq in EQUIPMENT_TYPES:
            if eq["key"] == self.equipment_key: return eq.get("name_en", self.equipment_key)
        return self.equipment_key