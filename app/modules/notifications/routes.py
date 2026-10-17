"""مسارات الإشعارات والتنبيهات."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.modules.contracts.models import Contract
from app.modules.suppliers.models import Supplier
from app.modules.missions.models import Mission
from app.modules.invoices.models import Invoice

bp = Blueprint("notifications", __name__)


def _get_all_alerts():
    """يجمع كل التنبيهات من كل الوحدات."""
    today = datetime.utcnow().date()
    cutoff_30 = today + timedelta(days=30)
    cutoff_7 = today + timedelta(days=7)

    alerts = {
        "expiring_contracts": [],
        "expired_contracts": [],
        "expiring_licenses": [],
        "expired_licenses": [],
        "overdue_invoices": [],
        "pending_signatures": [],
        "stuck_missions": [],
        "unpaid_invoices": [],
    }

    # ---------- عقود تنتهي خلال 30 يوم ----------
    expiring_contracts = Contract.query.filter(
        Contract.end_date.isnot(None),
        Contract.end_date >= today,
        Contract.end_date <= cutoff_30,
        Contract.status.in_(["active", "expiring"]),
    ).order_by(Contract.end_date).all()

    for c in expiring_contracts:
        days = (c.end_date - today).days
        alerts["expiring_contracts"].append({
            "contract": c,
            "days": days,
            "severity": "danger" if days <= 7 else "warning",
        })

    # ---------- عقود منتهية ----------
    expired_contracts = Contract.query.filter(
        Contract.end_date.isnot(None),
        Contract.end_date < today,
        Contract.status.in_(["active", "expiring"]),
    ).order_by(Contract.end_date.desc()).all()

    for c in expired_contracts:
        days = (today - c.end_date).days
        alerts["expired_contracts"].append({
            "contract": c,
            "days_overdue": days,
            "severity": "danger",
        })

    # ---------- رخص تجارية ----------
    expiring = Supplier.query.filter(
        Supplier.trade_license_expiry.isnot(None),
        Supplier.trade_license_expiry >= today,
        Supplier.trade_license_expiry <= cutoff_30,
        Supplier.status == "active",
    ).order_by(Supplier.trade_license_expiry).all()

    for s in expiring:
        days = (s.trade_license_expiry - today).days
        alerts["expiring_licenses"].append({
            "supplier": s,
            "days": days,
            "severity": "danger" if days <= 7 else "warning",
        })

    expired_lic = Supplier.query.filter(
        Supplier.trade_license_expiry.isnot(None),
        Supplier.trade_license_expiry < today,
        Supplier.status == "active",
    ).order_by(Supplier.trade_license_expiry.desc()).all()

    for s in expired_lic:
        days = (today - s.trade_license_expiry).days
        alerts["expired_licenses"].append({
            "supplier": s,
            "days_overdue": days,
            "severity": "danger",
        })

    # ---------- فواتير متأخرة ----------
    overdue = Invoice.query.filter(
        Invoice.due_date.isnot(None),
        Invoice.due_date < today,
        Invoice.status.in_(["submitted", "approved"]),
    ).order_by(Invoice.due_date).all()

    for inv in overdue:
        days = (today - inv.due_date).days
        alerts["overdue_invoices"].append({
            "invoice": inv,
            "days_overdue": days,
            "severity": "danger" if days > 30 else "warning",
        })

    # ---------- توقيعات بانتظار الاعتماد ----------
    pending_sig = Supplier.query.filter(
        Supplier.signature_file.isnot(None),
        Supplier.signature_approved == False,
    ).all()

    for s in pending_sig:
        alerts["pending_signatures"].append({
            "supplier": s,
            "severity": "warning",
        })

    # ---------- مهام متأخرة (بدأت ولم تنته خلال 24 ساعة) ----------
    yesterday = datetime.utcnow() - timedelta(hours=24)
    stuck = Mission.query.filter(
        Mission.status == "in_progress",
        Mission.started_at.isnot(None),
        Mission.started_at < yesterday,
    ).all()

    for m in stuck:
        hours = int((datetime.utcnow() - m.started_at).total_seconds() / 3600)
        alerts["stuck_missions"].append({
            "mission": m,
            "hours": hours,
            "severity": "warning",
        })

    return alerts


def _count_total(alerts):
    return sum(len(v) for v in alerts.values())


# ============================================================
#  Notifications Center
# ============================================================
@bp.route("/")
@login_required
def index():
    alerts = _get_all_alerts()
    total = _count_total(alerts)
    return render_template(
        "notifications/index.html",
        alerts=alerts,
        total=total,
    )


# ============================================================
#  API: count for navbar badge
# ============================================================
@bp.route("/api/count")
@login_required
def api_count():
    alerts = _get_all_alerts()
    counts = {k: len(v) for k, v in alerts.items()}
    return jsonify({
        "total": sum(counts.values()),
        "by_type": counts,
    })