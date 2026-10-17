"""
موديل الموردين.
"""
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.core.mixins import TimestampMixin


class Supplier(db.Model, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ============ بيانات الشركة ============
    company_name_ar: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True
    )
    company_name_en: Mapped[str] = mapped_column(String(200), nullable=True)
    trade_license_no: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False, index=True
    )
    trade_license_expiry: Mapped[datetime] = mapped_column(Date, nullable=True)
    trade_license_file: Mapped[str] = mapped_column(String(255), nullable=True)
    trade_license_uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    transport_permit_no: Mapped[str] = mapped_column(String(80), nullable=True)

    # ============ التواصل ============
    contact_person: Mapped[str] = mapped_column(String(120), nullable=True)
    phone: Mapped[str] = mapped_column(String(40), nullable=True)
    email: Mapped[str] = mapped_column(String(120), nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=True)

    # ============ البنك ============
    bank_name: Mapped[str] = mapped_column(String(120), nullable=True)
    iban: Mapped[str] = mapped_column(String(60), nullable=True)

    # ============ الضريبة ============
    vat_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trn: Mapped[str] = mapped_column(String(30), nullable=True)
    tax_certificate_file: Mapped[str] = mapped_column(String(255), nullable=True)
    tax_certificate_expiry: Mapped[datetime] = mapped_column(Date, nullable=True)

    # ============ التوقيع المعتمد ============
    authorized_signatory_name: Mapped[str] = mapped_column(String(120), nullable=True)
    authorized_signatory_title: Mapped[str] = mapped_column(String(120), nullable=True)
    signature_file: Mapped[str] = mapped_column(String(255), nullable=True)
    signature_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signature_approved_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    signature_approved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    signature_approved_by = relationship("User", foreign_keys=[signature_approved_by_id])

    # ============ الحالة ============
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # ============ Helpers ============
    @property
    def display_name(self) -> str:
        return self.company_name_ar or self.company_name_en or f"مورد #{self.id}"

    def license_status(self) -> str:
        """يعيد: valid / soon / expired / unknown"""
        if not self.trade_license_expiry:
            return "unknown"
        delta = (self.trade_license_expiry - datetime.utcnow().date()).days
        if delta < 0:
            return "expired"
        if delta <= 30:
            return "soon"
        return "valid"

    def license_days_left(self) -> int:
        if not self.trade_license_expiry:
            return 0
        return (self.trade_license_expiry - datetime.utcnow().date()).days

    def tax_status(self) -> str:
        if not self.vat_registered:
            return "not_registered"
        if not self.tax_certificate_expiry:
            return "unknown"
        delta = (self.tax_certificate_expiry - datetime.utcnow().date()).days
        if delta < 0:
            return "expired"
        if delta <= 30:
            return "soon"
        return "valid"

    def is_license_valid(self) -> bool:
        return self.license_status() == "valid"

    def is_signature_ready(self) -> bool:
        return bool(self.signature_file and self.signature_approved)

    def __repr__(self):
        return f"<Supplier {self.company_name_ar}>"