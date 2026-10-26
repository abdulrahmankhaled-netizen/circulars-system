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
#  Profit Analysis (Smart & Detailed)
# ============================================================
# ============================================================
#  Profit Analysis (Smart & Detailed)
# ============================================================
@bp.route("/profit")
@login_required
@require_permission("reports.view")
def profit():
    """تحليل الأرباح (المتقدم)."""
    from_date, to_date, period = _get_date_range()
    
    # ⭐ إعدادات الفلترة والتجميع الجديدة
    group_by = request.args.get("group_by", "contract")
    filter_month = request.args.get("filter_month", "").strip()
    filter_supplier = request.args.get("filter_supplier", "").strip()

    # 1. جلب المهام في الفترة المحددة
    q = Mission.query
    q = _filter_missions_query(q, from_date, to_date)
    missions = q.all()

    # تطبيق فلاتر الشهر والمورد
    if filter_supplier:
        try:
            sid = int(filter_supplier)
            missions = [m for m in missions if m.contract and m.contract.supplier_id == sid]
        except ValueError:
            pass

    if filter_month:
        missions = [m for m in missions if m.mission_date and m.mission_date.strftime('%Y-%m') == filter_month]

    # 2. حساب الإجماليات الأساسية
    total_revenue = sum(m.revenue or 0 for m in missions)
    total_var_cost = sum(m.cost or 0 for m in missions)
    collected_revenue = sum(m.revenue or 0 for m in missions if m.customer_invoice_status == 'paid')
    pending_revenue = total_revenue - collected_revenue

    contracts = Contract.query.all()
    total_fixed_cost = 0
    for c in contracts:
        c_missions = [m for m in missions if m.contract_id == c.id]
        if len(c_missions) > 0:
            total_fixed_cost += c.calculated_value

    total_cost = total_var_cost + total_fixed_cost
    expected_profit = total_revenue - total_cost
    actual_profit = collected_revenue - total_cost
    
    expected_margin = (expected_profit / total_revenue * 100) if total_revenue else 0
    actual_margin = (actual_profit / collected_revenue * 100) if collected_revenue else 0

    totals = {
        "missions": len(missions), "revenue": total_revenue, "collected_revenue": collected_revenue,
        "pending_revenue": pending_revenue, "var_cost": total_var_cost, "fixed_cost": total_fixed_cost,
        "cost": total_cost, "expected_profit": expected_profit, "actual_profit": actual_profit,
        "expected_margin": round(expected_margin, 1), "actual_margin": round(actual_margin, 1),
    }

    # 3. بناء البيانات الشجرية (Tree View)
    grouped_data = []
    suppliers = Supplier.query.filter_by(status="active").order_by(Supplier.company_name_ar).all()

    if group_by == "contract":
        contracts_dict = {}
        for m in missions:
            if not m.contract_id: continue
            if m.contract_id not in contracts_dict:
                contracts_dict[m.contract_id] = {"contract": m.contract, "missions": [], "months": {}}
            contracts_dict[m.contract_id]["missions"].append(m)
            month_key = m.mission_date.strftime("%Y-%m") if m.mission_date else "غير محدد"
            if month_key not in contracts_dict[m.contract_id]["months"]:
                contracts_dict[m.contract_id]["months"][month_key] = []
            contracts_dict[m.contract_id]["months"][month_key].append(m)

        for cid, data in contracts_dict.items():
            c = data["contract"]
            c_totals = {k: 0 for k in ["revenue", "collected_revenue", "pending_revenue", "var_cost", "fixed_cost", "total_cost", "expected_profit", "actual_profit"]}
            children = []

            # حساب التكلفة الثابتة الشهرية للعقد
            c_fixed = 0
            for item in c.equipment_items:
                if item.pricing_period in ['monthly', 'annual']:
                    cost = (item.quantity or 1) * (item.unit_price or 0)
                    if item.pricing_period == 'annual': cost /= 12
                    c_fixed += cost

            for month_key, m_list in sorted(data["months"].items()):
                m_rev = sum(m.revenue or 0 for m in m_list)
                m_col = sum(m.revenue or 0 for m in m_list if m.customer_invoice_status == 'paid')
                m_var = sum(m.cost or 0 for m in m_list)
                m_total_cost = m_var + c_fixed

                child = {
                    "name": month_key, "missions": len(m_list), "revenue": m_rev, "collected_revenue": m_col,
                    "pending_revenue": m_rev - m_col, "var_cost": m_var, "fixed_cost": c_fixed,
                    "total_cost": m_total_cost, "expected_profit": m_rev - m_total_cost, "actual_profit": m_col - m_total_cost
                }
                children.append(child)

                c_totals["revenue"] += m_rev
                c_totals["collected_revenue"] += m_col
                c_totals["var_cost"] += m_var
                c_totals["fixed_cost"] += c_fixed
                c_totals["total_cost"] += m_total_cost

            c_totals["pending_revenue"] = c_totals["revenue"] - c_totals["collected_revenue"]
            c_totals["expected_profit"] = c_totals["revenue"] - c_totals["total_cost"]
            c_totals["actual_profit"] = c_totals["collected_revenue"] - c_totals["total_cost"]
            c_totals["missions"] = len(data["missions"])

            grouped_data.append({
                "group_name": f"{c.contract_number} - {c.supplier.company_name_ar}",
                "totals": c_totals, "children": children
            })

    elif group_by == "month":
        months_dict = {}
        for m in missions:
            if not m.mission_date: continue
            month_key = m.mission_date.strftime("%Y-%m")
            if month_key not in months_dict:
                months_dict[month_key] = {"missions": [], "contracts": {}}
            months_dict[month_key]["missions"].append(m)

            cid = m.contract_id
            if cid not in months_dict[month_key]["contracts"]:
                months_dict[month_key]["contracts"][cid] = {"contract": m.contract, "missions": []}
            months_dict[month_key]["contracts"][cid]["missions"].append(m)

        for month_key, data in sorted(months_dict.items(), reverse=True):
            m_totals = {k: 0 for k in ["revenue", "collected_revenue", "pending_revenue", "var_cost", "fixed_cost", "total_cost", "expected_profit", "actual_profit"]}
            children = []

            for cid, c_data in data["contracts"].items():
                c = c_data["contract"]
                c_missions = c_data["missions"]

                c_rev = sum(m.revenue or 0 for m in c_missions)
                c_col = sum(m.revenue or 0 for m in c_missions if m.customer_invoice_status == 'paid')
                c_var = sum(m.cost or 0 for m in c_missions)

                c_fixed = 0
                for item in c.equipment_items:
                    if item.pricing_period in ['monthly', 'annual']:
                        cost = (item.quantity or 1) * (item.unit_price or 0)
                        if item.pricing_period == 'annual': cost /= 12
                        c_fixed += cost

                c_total_cost = c_var + c_fixed

                child = {
                    "name": f"{c.contract_number} - {c.supplier.company_name_ar}", "missions": len(c_missions),
                    "revenue": c_rev, "collected_revenue": c_col, "pending_revenue": c_rev - c_col,
                    "var_cost": c_var, "fixed_cost": c_fixed, "total_cost": c_total_cost,
                    "expected_profit": c_rev - c_total_cost, "actual_profit": c_col - c_total_cost
                }
                children.append(child)

                m_totals["revenue"] += c_rev
                m_totals["collected_revenue"] += c_col
                m_totals["var_cost"] += c_var
                m_totals["fixed_cost"] += c_fixed
                m_totals["total_cost"] += c_total_cost

            m_totals["pending_revenue"] = m_totals["revenue"] - m_totals["collected_revenue"]
            m_totals["expected_profit"] = m_totals["revenue"] - m_totals["total_cost"]
            m_totals["actual_profit"] = m_totals["collected_revenue"] - m_totals["total_cost"]
            m_totals["missions"] = len(data["missions"])

            grouped_data.append({
                "group_name": month_key,
                "totals": m_totals, "children": children
            })

    return render_template(
        "reports/profit.html",
        totals=totals,
        grouped_data=grouped_data,
        group_by=group_by,
        filter_month=filter_month,
        filter_supplier=filter_supplier,
        suppliers=suppliers,
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

    by_status = {}
    for m in missions:
        by_status[m.status] = by_status.get(m.status, 0) + 1

    by_equipment = {}
    for m in missions:
        key = m.equipment_key
        by_equipment[key] = by_equipment.get(key, 0) + 1

    by_region = {}
    for m in missions:
        key = m.region or "(بدون)"
        by_region[key] = by_region.get(key, 0) + 1

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
        missions_q = Mission.query.join(Contract).filter(Contract.supplier_id == s.id)
        missions_q = _filter_missions_query(missions_q, from_date, to_date)
        missions = missions_q.all()

        revenue = sum(m.revenue or 0 for m in missions)
        collected_revenue = sum(m.revenue or 0 for m in missions if m.customer_invoice_status == 'paid')
        cost = sum(m.cost or 0 for m in missions)
        
        expected_profit = revenue - cost
        actual_profit = collected_revenue - cost
        margin = (expected_profit / revenue * 100) if revenue else 0

        invoices = Invoice.query.filter_by(supplier_id=s.id).all()
        total_invoiced = sum(i.total_amount or 0 for i in invoices)
        paid_invoices = sum(i.total_amount or 0 for i in invoices if i.status == "paid")

        completed = sum(1 for m in missions if m.status in ("completed", "verified", "paid"))
        success_rate = (completed / len(missions) * 100) if missions else 0

        results.append({
            "supplier": s,
            "missions": len(missions),
            "revenue": revenue,
            "collected_revenue": collected_revenue,
            "cost": cost,
            "expected_profit": expected_profit,
            "actual_profit": actual_profit,
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
        "اللوحة", "المنطقة", "الحالة", "حالة الدفع",
        "التكلفة", "الإيراد", "الربح المتوقع", "الهامش %",
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
        ws.cell(row=i, column=9, value=m.customer_invoice_label() if hasattr(m, 'customer_invoice_label') else m.customer_invoice_status)
        ws.cell(row=i, column=10, value=cost)
        ws.cell(row=i, column=11, value=revenue)
        ws.cell(row=i, column=12, value=profit)
        ws.cell(row=i, column=13, value=round(margin, 1))

    widths = [14, 12, 16, 25, 20, 14, 14, 12, 14, 12, 12, 12, 10]
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