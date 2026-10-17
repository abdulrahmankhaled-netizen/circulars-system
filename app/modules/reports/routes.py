"""مسارات التقارير والتحليلات."""
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    send_file, flash,
)
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.core.permissions import require_permission
from app.modules.contracts.models import Contract
from app.modules.suppliers.models import Supplier
from app.modules.missions.models import Mission
from app.modules.invoices.models import Invoice

bp = Blueprint("reports", __name__)


# ============================================================
#  Helper: date range from query
# ============================================================
def _get_date_range():
    """يستخرج from_date و to_date من الرابط."""
    today = datetime.utcnow().date()
    period = request.args.get("period", "").strip()

    from_date = None
    to_date = None

    if period == "today":
        from_date = to_date = today
    elif period == "this_week":
        from_date = today - timedelta(days=today.weekday())
        to_date = today
    elif period == "this_month":
        from_date = today.replace(day=1)
        to_date = today
    elif period == "last_month":
        first = today.replace(day=1)
        last = first - timedelta(days=1)
        from_date = last.replace(day=1)
        to_date = last
    elif period == "last_30":
        from_date = today - timedelta(days=30)
        to_date = today
    elif period == "last_7":
        from_date = today - timedelta(days=7)
        to_date = today
    elif period == "this_year":
        from_date = today.replace(month=1, day=1)
        to_date = today
    else:
        fs = request.args.get("from_date", "").strip()
        ts = request.args.get("to_date", "").strip()
        if fs:
            try:
                from_date = datetime.strptime(fs, "%Y-%m-%d").date()
            except ValueError:
                pass
        if ts:
            try:
                to_date = datetime.strptime(ts, "%Y-%m-%d").date()
            except ValueError:
                pass

    return from_date, to_date, period


def _filter_missions_query(query, from_date, to_date):
    if from_date:
        query = query.filter(
            func.date(Mission.mission_date) >= from_date.isoformat()
        )
    if to_date:
        query = query.filter(
            func.date(Mission.mission_date) <= to_date.isoformat()
        )
    return query


# ============================================================
#  Reports Home
# ============================================================
@bp.route("/")
@login_required
def index():
    """صفحة التقارير الرئيسية."""
    return render_template("reports/index.html")


# ============================================================
#  Profit Analysis
# ============================================================
@bp.route("/profit")
@login_required
@require_permission("reports.view")
def profit():
    """تحليل الأرباح."""
    from_date, to_date, period = _get_date_range()

    # كل المهام
    q = Mission.query
    q = _filter_missions_query(q, from_date, to_date)
    missions = q.all()

    # إجماليات
    total_revenue = sum(m.revenue or 0 for m in missions)
    total_cost = sum(m.cost or 0 for m in missions)
    total_profit = total_revenue - total_cost
    profit_margin = (total_profit / total_revenue * 100) if total_revenue else 0

    totals = {
        "missions": len(missions),
        "revenue": total_revenue,
        "cost": total_cost,
        "profit": total_profit,
        "margin": round(profit_margin, 1),
    }

    # حسب العقد
    by_contract = {}
    for m in missions:
        key = m.contract_id
        if key not in by_contract:
            by_contract[key] = {
                "contract": m.contract,
                "missions": 0,
                "revenue": 0,
                "cost": 0,
            }
        by_contract[key]["missions"] += 1
        by_contract[key]["revenue"] += (m.revenue or 0)
        by_contract[key]["cost"] += (m.cost or 0)

    per_contract = []
    for v in by_contract.values():
        v["profit"] = v["revenue"] - v["cost"]
        v["margin"] = round((v["profit"] / v["revenue"] * 100) if v["revenue"] else 0, 1)
        per_contract.append(v)
    per_contract.sort(key=lambda x: x["revenue"], reverse=True)

    # حسب المورد
    by_supplier = {}
    for m in missions:
        if not m.contract or not m.contract.supplier:
            continue
        key = m.contract.supplier_id
        if key not in by_supplier:
            by_supplier[key] = {
                "supplier": m.contract.supplier,
                "missions": 0,
                "revenue": 0,
                "cost": 0,
            }
        by_supplier[key]["missions"] += 1
        by_supplier[key]["revenue"] += (m.revenue or 0)
        by_supplier[key]["cost"] += (m.cost or 0)

    per_supplier = []
    for v in by_supplier.values():
        v["profit"] = v["revenue"] - v["cost"]
        v["margin"] = round((v["profit"] / v["revenue"] * 100) if v["revenue"] else 0, 1)
        per_supplier.append(v)
    per_supplier.sort(key=lambda x: x["revenue"], reverse=True)

    # حسب المعدة
    by_equipment = {}
    for m in missions:
        key = m.equipment_key
        if key not in by_equipment:
            by_equipment[key] = {
                "key": key,
                "name": m.equipment_name_ar(),
                "missions": 0,
                "revenue": 0,
                "cost": 0,
            }
        by_equipment[key]["missions"] += 1
        by_equipment[key]["revenue"] += (m.revenue or 0)
        by_equipment[key]["cost"] += (m.cost or 0)

    per_equipment = []
    for v in by_equipment.values():
        v["profit"] = v["revenue"] - v["cost"]
        v["margin"] = round((v["profit"] / v["revenue"] * 100) if v["revenue"] else 0, 1)
        per_equipment.append(v)
    per_equipment.sort(key=lambda x: x["missions"], reverse=True)

    # حسب الشهر
    by_month = {}
    for m in missions:
        if not m.mission_date:
            continue
        key = m.mission_date.strftime("%Y-%m")
        if key not in by_month:
            by_month[key] = {"month": key, "missions": 0, "revenue": 0, "cost": 0}
        by_month[key]["missions"] += 1
        by_month[key]["revenue"] += (m.revenue or 0)
        by_month[key]["cost"] += (m.cost or 0)

    per_month = []
    for v in sorted(by_month.values(), key=lambda x: x["month"]):
        v["profit"] = v["revenue"] - v["cost"]
        per_month.append(v)

    return render_template(
        "reports/profit.html",
        totals=totals,
        per_contract=per_contract,
        per_supplier=per_supplier,
        per_equipment=per_equipment,
        per_month=per_month,
        from_date=from_date.strftime("%Y-%m-%d") if from_date else "",
        to_date=to_date.strftime("%Y-%m-%d") if to_date else "",
        period=period,
    )


# ============================================================
#  Missions Report
# ============================================================
@bp.route("/missions")
@login_required
@require_permission("reports.view")
def missions_report():
    from_date, to_date, period = _get_date_range()

    q = Mission.query
    q = _filter_missions_query(q, from_date, to_date)
    missions = q.all()

    # حسب الحالة
    by_status = {}
    for m in missions:
        by_status[m.status] = by_status.get(m.status, 0) + 1

    # حسب المعدة
    by_equipment = {}
    for m in missions:
        key = m.equipment_key
        by_equipment[key] = by_equipment.get(key, 0) + 1

    # حسب المنطقة
    by_region = {}
    for m in missions:
        key = m.region or "(بدون)"
        by_region[key] = by_region.get(key, 0) + 1

    # حسب السائق
    by_driver = {}
    for m in missions:
        if m.driver_name:
            by_driver[m.driver_name] = by_driver.get(m.driver_name, 0) + 1

    stats = {
        "total": len(missions),
        "completed": sum(1 for m in missions if m.status == "completed"),
        "verified": sum(1 for m in missions if m.status == "verified"),
        "paid": sum(1 for m in missions if m.status == "paid"),
        "failed": sum(1 for m in missions if m.status == "failed"),
    }

    return render_template(
        "reports/missions.html",
        stats=stats,
        by_status=by_status,
        by_equipment=sorted(by_equipment.items(), key=lambda x: -x[1]),
        by_region=sorted(by_region.items(), key=lambda x: -x[1]),
        by_driver=sorted(by_driver.items(), key=lambda x: -x[1])[:20],
        from_date=from_date.strftime("%Y-%m-%d") if from_date else "",
        to_date=to_date.strftime("%Y-%m-%d") if to_date else "",
        period=period,
    )


# ============================================================
#  Suppliers Performance
# ============================================================
@bp.route("/suppliers")
@login_required
@require_permission("reports.view")
def suppliers_report():
    from_date, to_date, period = _get_date_range()

    suppliers = Supplier.query.filter_by(status="active")\
        .order_by(Supplier.company_name_ar).all()

    results = []
    for s in suppliers:
        # مهام هذا المورد
        missions_q = Mission.query.join(Contract).filter(Contract.supplier_id == s.id)
        missions_q = _filter_missions_query(missions_q, from_date, to_date)
        missions = missions_q.all()

        revenue = sum(m.revenue or 0 for m in missions)
        cost = sum(m.cost or 0 for m in missions)
        profit = revenue - cost
        margin = (profit / revenue * 100) if revenue else 0

        # فواتير المورد
        invoices = Invoice.query.filter_by(supplier_id=s.id).all()
        total_invoiced = sum(i.total_amount or 0 for i in invoices)
        paid_invoices = sum(i.total_amount or 0 for i in invoices if i.status == "paid")

        # معدل النجاح
        completed = sum(1 for m in missions if m.status in ("completed", "verified", "paid"))
        success_rate = (completed / len(missions) * 100) if missions else 0

        results.append({
            "supplier": s,
            "missions": len(missions),
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
            "margin": round(margin, 1),
            "total_invoiced": total_invoiced,
            "paid_invoices": paid_invoices,
            "success_rate": round(success_rate, 1),
        })

    results.sort(key=lambda x: x["revenue"], reverse=True)

    return render_template(
        "reports/suppliers.html",
        results=results,
        from_date=from_date.strftime("%Y-%m-%d") if from_date else "",
        to_date=to_date.strftime("%Y-%m-%d") if to_date else "",
        period=period,
    )


# ============================================================
#  Export Profit to Excel
# ============================================================
@bp.route("/export/profit")
@login_required
@require_permission("reports.view")
def export_profit():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    import io

    from_date, to_date, _ = _get_date_range()

    q = Mission.query
    q = _filter_missions_query(q, from_date, to_date)
    missions = q.all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Missions"
    ws.sheet_view.rightToLeft = True

    headers = [
        "رقم المهمة", "التاريخ", "العقد", "المورد", "المعدة",
        "اللوحة", "المنطقة", "الحالة",
        "التكلفة", "الإيراد", "الربح", "الهامش %",
    ]

    hfont = Font(bold=True, color="FFFFFF")
    hfill = PatternFill("solid", fgColor="1F4E78")
    center = Alignment(horizontal="center")

    for idx, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=idx, value=h)
        c.font = hfont
        c.fill = hfill
        c.alignment = center

    for i, m in enumerate(missions, 2):
        cost = m.cost or 0
        revenue = m.revenue or 0
        profit = revenue - cost
        margin = (profit / revenue * 100) if revenue else 0

        ws.cell(row=i, column=1, value=m.mission_number)
        ws.cell(row=i, column=2, value=m.mission_date.strftime("%Y-%m-%d") if m.mission_date else "")
        ws.cell(row=i, column=3, value=m.contract.contract_number if m.contract else "")
        ws.cell(row=i, column=4, value=m.contract.supplier.company_name_ar if m.contract and m.contract.supplier else "")
        ws.cell(row=i, column=5, value=m.equipment_name_ar())
        ws.cell(row=i, column=6, value=m.vehicle_plate or "")
        ws.cell(row=i, column=7, value=m.region or "")
        ws.cell(row=i, column=8, value=m.status)
        ws.cell(row=i, column=9, value=cost)
        ws.cell(row=i, column=10, value=revenue)
        ws.cell(row=i, column=11, value=profit)
        ws.cell(row=i, column=12, value=round(margin, 1))

    widths = [14, 12, 16, 25, 20, 14, 14, 12, 12, 12, 12, 10]
    for idx, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = w

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    return send_file(
        bio,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"profit_report_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.xlsx",
    )