"""
موديلات الفواتير.
تدعم نوعين: فاتورة مورد (نتلقاها) + فاتورة عميل (نرسلها).
"""
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Text, Float, Boolean, Date,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.core.mixins import TimestampMixin


class Invoice(db.Model, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False, index=True
    )

    # نوع الفاتورة: supplier | customer
    invoice_type: Mapped[str] = mapped_column(
        String(20), default="supplier", nullable=False, index=True
    )

    # العلاقات
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    supplier = relationship("Supplier", backref="invoices")

    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    contract = relationship("Contract", backref="invoices")

    mission_id: Mapped[int] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    mission = relationship("Mission", backref="invoices")

    # للفاتورة على العميل
    customer_name: Mapped[str] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(40), nullable=True)

    # التواريخ
    issue_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    due_date: Mapped[datetime] = mapped_column(Date, nullable=True)

    # المبالغ
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    vat_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="AED")

    # الحالة
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False, index=True
    )

    # المرفق
    pdf_path: Mapped[str] = mapped_column(String(255), nullable=True)
    pdf_uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # علاقات إضافية
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by = relationship("User", foreign_keys=[created_by_id])

    approved_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    approved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # ============ Helpers ============
    def type_label(self) -> str:
        return "مورد" if self.invoice_type == "supplier" else "عميل"

    def type_color(self) -> str:
        return "warning" if self.invoice_type == "supplier" else "primary"

    def status_label(self) -> str:
        labels = {
            "draft": "مسودة",
            "submitted": "مُقدّمة",
            "approved": "معتمدة",
            "paid": "مدفوعة",
            "disputed": "متنازع عليها",
            "cancelled": "ملغاة",
        }
        return labels.get(self.status, self.status)

    def status_color(self) -> str:
        colors = {
            "draft": "secondary",
            "submitted": "info",
            "approved": "primary",
            "paid": "success",
            "disputed": "danger",
            "cancelled": "secondary",
        }
        return colors.get(self.status, "secondary")

    def calculate_totals(self, vat_rate: float = 0.05):
        """يحسب الإجمالي من amount."""
        amt = self.amount or 0.0
        self.vat_amount = round(amt * vat_rate, 2)
        self.total_amount = round(amt + self.vat_amount, 2)

    def display_name(self) -> str:
        if self.invoice_type == "supplier" and self.supplier:
            return f"{self.invoice_number} — {self.supplier.company_name_ar}"
        if self.invoice_type == "customer" and self.customer_name:
            return f"{self.invoice_number} — {self.customer_name}"
        return self.invoice_number

    def __repr__(self):
        return f"<Invoice {self.invoice_number} ({self.invoice_type}/{self.status})>"