"""
لوحة تحكم عبقريّة — تحليل شامل + تنبؤ + مخاطر + توصيات.
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from collections import defaultdict
from statistics import mean

from app.extensions import db
from app.modules.users.models import User
from app.modules.suppliers.models import Supplier
from app.modules.contracts.models import Contract
from app.modules.missions.models import Mission
from app.modules.invoices.models import Invoice
from app.modules.requests.models import EquipmentRequest

bp = Blueprint("dashboard", __name__)


# ============================================================
#  Helpers
# ============================================================
def _month_key(dt):
    return dt.strftime("%Y-%m") if dt else None


def _shift_month(date_obj, months):
    """يُزيح تاريخاً بعدد أشهر."""
    m = date_obj.month - 1 + months
    y = date_obj.year + m // 12
    m = m % 12 + 1
    return date_obj.replace(year=y, month=m, day=1)


def _safe_div(a, b, default=0):
    return (a / b) if b else default


def _trend_pct(current, previous):
    """نسبة التغير %."""
    if not previous:
        return 100 if current > 0 else 0
    return round((current - previous) / previous * 100, 1)


# ============================================================
#  Financial KPIs with Trends
# ============================================================
def _get_financial_kpis():
    today = datetime.utcnow().date()
    this_month_start = today.replace(day=1)
    prev_month_end = this_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    # ============ الإجمالي ============
    total = {
        "revenue": float(db.session.query(
            func.coalesce(func.sum(Mission.revenue), 0)
        ).scalar() or 0),
        "cost": float(db.session.query(
            func.coalesce(func.sum(Mission.cost), 0)
        ).scalar() or 0),
        "missions": Mission.query.count(),
    }
    total["profit"] = total["revenue"] - total["cost"]
    total["margin"] = round(_safe_div(total["profit"], total["revenue"]) * 100, 1)

    # ============ الشهر الحالي ============
    tm = Mission.query.filter(
        Mission.mission_date >= datetime.combine(this_month_start, datetime.min.time()),
    ).all()
    this_month = {
        "revenue": sum(m.revenue or 0 for m in tm),
        "cost": sum(m.cost or 0 for m in tm),
        "missions": len(tm),
    }
    this_month["profit"] = this_month["revenue"] - this_month["cost"]
    this_month["margin"] = round(_safe_div(this_month["profit"], this_month["revenue"]) * 100, 1)

    # ============ الشهر الماضي ============
    pm = Mission.query.filter(
        Mission.mission_date >= datetime.combine(prev_month_start, datetime.min.time()),
        Mission.mission_date <= datetime.combine(prev_month_end, datetime.max.time()),
    ).all()
    prev_month = {
        "revenue": sum(m.revenue or 0 for m in pm),
        "cost": sum(m.cost or 0 for m in pm),
        "missions": len(pm),
    }
    prev_month["profit"] = prev_month["revenue"] - prev_month["cost"]
    prev_month["margin"] = round(_safe_div(prev_month["profit"], prev_month["revenue"]) * 100, 1)

    # ============ الاتجاهات ============
    trends = {
        "revenue": _trend_pct(this_month["revenue"], prev_month["revenue"]),
        "cost": _trend_pct(this_month["cost"], prev_month["cost"]),
        "profit": _trend_pct(this_month["profit"], prev_month["profit"]),
        "missions": _trend_pct(this_month["missions"], prev_month["missions"]),
    }

    return {
        "total": total,
        "this_month": this_month,
        "prev_month": prev_month,
        "trends": trends,
    }


# ============================================================
#  Monthly Revenue (12 months)
# ============================================================
def _get_monthly_revenue(months_back=12):
    today = datetime.utcnow().date()
    labels = []
    revenue_data = []
    cost_data = []
    profit_data = []
    missions_data = []

    for i in range(months_back - 1, -1, -1):
        target = _shift_month(today, -i)
        next_month = _shift_month(target, 1)

        ms = Mission.query.filter(
            Mission.mission_date >= datetime.combine(target, datetime.min.time()),
            Mission.mission_date < datetime.combine(next_month, datetime.min.time()),
        ).all()

        rev = sum(m.revenue or 0 for m in ms)
        cost = sum(m.cost or 0 for m in ms)

        labels.append(target.strftime("%b %Y"))
        revenue_data.append(round(rev, 2))
        cost_data.append(round(cost, 2))
        profit_data.append(round(rev - cost, 2))
        missions_data.append(len(ms))

    return {
        "labels": labels,
        "revenue": revenue_data,
        "cost": cost_data,
        "profit": profit_data,
        "missions": missions_data,
    }


# ============================================================
#  Missions per Project (Contract)
# ============================================================
def _get_project_stats():
    contracts = Contract.query.all()
    results = []

    for c in contracts:
        missions = Mission.query.filter_by(contract_id=c.id).all()
        if not missions:
            continue

        revenue = sum(m.revenue or 0 for m in missions)
        cost = sum(m.cost or 0 for m in missions)

        results.append({
            "number": c.contract_number,
            "supplier": c.supplier.company_name_ar if c.supplier else "—",
            "region": c.region or "—",
            "missions": len(missions),
            "revenue": revenue,
            "cost": cost,
            "profit": revenue - cost,
        })

    results.sort(key=lambda x: x["missions"], reverse=True)
    return results


# ============================================================
#  Equipment Distribution
# ============================================================
def _get_equipment_stats():
    missions = Mission.query.all()
    counter = defaultdict(lambda: {"count": 0, "revenue": 0})

    for m in missions:
        key = m.equipment_name_ar() or m.equipment_key or "غير محدد"
        counter[key]["count"] += 1
        counter[key]["revenue"] += m.revenue or 0

    results = [
        {"name": k, "count": v["count"], "revenue": v["revenue"]}
        for k, v in counter.items()
    ]
    results.sort(key=lambda x: x["count"], reverse=True)
    return results[:10]


# ============================================================
#  Payment Status
# ============================================================
def _get_payment_stats():
    missions = Mission.query.all()
    supplier = {"paid": 0, "pending": 0, "cancelled": 0}
    customer = {"paid": 0, "pending": 0, "invoiced": 0, "cancelled": 0}

    for m in missions:
        sp = m.supplier_payment_status or "pending"
        cp = m.customer_invoice_status or "pending"
        if sp in supplier:
            supplier[sp] += 1
        if cp in customer:
            customer[cp] += 1

    return {"supplier": supplier, "customer": customer}


# ============================================================
#  Top Suppliers
# ============================================================
def _get_supplier_performance(limit=5):
    results = []
    for s in Supplier.query.filter_by(status="active").all():
        missions = Mission.query.join(Contract).filter(Contract.supplier_id == s.id).all()
        if not missions:
            continue
        revenue = sum(m.revenue or 0 for m in missions)
        cost = sum(m.cost or 0 for m in missions)
        profit = revenue - cost
        margin = _safe_div(profit, revenue) * 100

        results.append({
            "name": s.company_name_ar,
            "id": s.id,
            "missions": len(missions),
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
            "margin": round(margin, 1),
        })

    results.sort(key=lambda x: x["revenue"], reverse=True)
    return results[:limit]


# ============================================================
#  Top Drivers
# ============================================================
def _get_driver_performance(limit=5):
    counter = defaultdict(lambda: {"missions": 0, "revenue": 0})
    for m in Mission.query.all():
        if not m.driver_name:
            continue
        key = m.driver_name.split("(")[0].strip()
        counter[key]["missions"] += 1
        counter[key]["revenue"] += m.revenue or 0

    results = [
        {"name": k, "missions": v["missions"], "revenue": v["revenue"]}
        for k, v in counter.items()
    ]
    results.sort(key=lambda x: x["missions"], reverse=True)
    return results[:limit]


# ============================================================
#  Risks Analysis
# ============================================================
def _get_risks():
    today = datetime.utcnow().date()
    cutoff = today + timedelta(days=30)

    risks = {
        "expired_contracts": 0,
        "expiring_contracts": 0,
        "expired_licenses": 0,
        "expiring_licenses": 0,
        "overdue_invoices": 0,
        "unpaid_total": 0,
        "stuck_missions": 0,
        "total_score": 0,
    }

    risks["expired_contracts"] = Contract.query.filter(
        Contract.end_date.isnot(None),
        Contract.end_date < today,
        Contract.status.in_(["active", "expiring"]),
    ).count()

    risks["expiring_contracts"] = Contract.query.filter(
        Contract.end_date.isnot(None),
        Contract.end_date >= today,
        Contract.end_date <= cutoff,
        Contract.status.in_(["active", "expiring"]),
    ).count()

    risks["expired_licenses"] = Supplier.query.filter(
        Supplier.trade_license_expiry.isnot(None),
        Supplier.trade_license_expiry < today,
        Supplier.status == "active",
    ).count()

    risks["expiring_licenses"] = Supplier.query.filter(
        Supplier.trade_license_expiry.isnot(None),
        Supplier.trade_license_expiry >= today,
        Supplier.trade_license_expiry <= cutoff,
        Supplier.status == "active",
    ).count()

    overdue = Invoice.query.filter(
        Invoice.due_date.isnot(None),
        Invoice.due_date < today,
        Invoice.status.in_(["submitted", "approved"]),
    ).all()
    risks["overdue_invoices"] = len(overdue)
    risks["unpaid_total"] = sum(i.total_amount or 0 for i in overdue)

    yesterday = datetime.utcnow() - timedelta(hours=24)
    risks["stuck_missions"] = Mission.query.filter(
        Mission.status == "in_progress",
        Mission.started_at.isnot(None),
        Mission.started_at < yesterday,
    ).count()

    # حساب درجة المخاطر (0-100، كلما زادت زاد الخطر)
    score = (
        risks["expired_contracts"] * 15 +
        risks["expiring_contracts"] * 5 +
        risks["expired_licenses"] * 10 +
        risks["expiring_licenses"] * 3 +
        risks["overdue_invoices"] * 8 +
        risks["stuck_missions"] * 5
    )
    risks["total_score"] = min(100, score)

    if risks["total_score"] >= 70:
        risks["level"] = "حرج"
        risks["color"] = "danger"
    elif risks["total_score"] >= 40:
        risks["level"] = "مرتفع"
        risks["color"] = "warning"
    elif risks["total_score"] >= 20:
        risks["level"] = "متوسط"
        risks["color"] = "info"
    else:
        risks["level"] = "منخفض"
        risks["color"] = "success"

    return risks


# ============================================================
#  Predictions (Linear Regression on 6 months)
# ============================================================
def _predict_next_months():
    monthly = _get_monthly_revenue(months_back=6)
    values = monthly["revenue"]

    if len(values) < 3 or sum(values) == 0:
        return {"labels": [], "values": [], "trend": "flat", "confidence": 0}

    # Linear Regression بسيط
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = mean(values)
    num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n)) or 1
    b = num / den
    a = y_mean - b * x_mean

    # تنبؤ 3 أشهر
    today = datetime.utcnow().date()
    labels = []
    predictions = []
    for i in range(1, 4):
        future = _shift_month(today, i)
        labels.append(future.strftime("%b %Y"))
        predictions.append(max(0, round(a + b * (n + i - 1), 2)))

    # اتجاه
    if b > 1000:
        trend = "up"
        trend_label = "نمو"
        trend_color = "success"
    elif b < -1000:
        trend = "down"
        trend_label = "انخفاض"
        trend_color = "danger"
    else:
        trend = "flat"
        trend_label = "مستقر"
        trend_color = "secondary"

    # ثقة التنبؤ
    if len(values) >= 6 and all(v > 0 for v in values):
        confidence = min(95, 60 + len(values) * 5)
    else:
        confidence = 40

    return {
        "labels": labels,
        "values": predictions,
        "trend": trend,
        "trend_label": trend_label,
        "trend_color": trend_color,
        "confidence": confidence,
        "slope": round(b, 2),
    }


# ============================================================
#  Smart Insights & Recommendations
# ============================================================
def _get_insights():
    insights = []
    today = datetime.utcnow().date()

    # ============ 1. المورد الأكثر ربحية ============
    top_suppliers = _get_supplier_performance(limit=10)
    if top_suppliers:
        best = max(top_suppliers, key=lambda x: x["profit"])
        if best["profit"] > 0:
            insights.append({
                "type": "success",
                "icon": "trophy",
                "title": f"المورد الأعلى ربحية: {best['name']}",
                "message": f"ربح صافي {best['profit']:,.0f} AED (هامش {best['margin']}%). "
                           f"يُنصح بزيادة حجم التعامل معه.",
            })

    # ============ 2. عقد ضعيف/خاسر ============
    projects = _get_project_stats()
    losing = [p for p in projects if p["profit"] < 0 and p["missions"] >= 3]
    if losing:
        worst = min(losing, key=lambda x: x["profit"])
        insights.append({
            "type": "danger",
            "icon": "exclamation-triangle",
            "title": f"عقد خاسر: {worst['number']}",
            "message": f"خسارة {abs(worst['profit']):,.0f} AED على {worst['missions']} مهمة. "
                       f"راجع التسعير مع {worst['supplier']}.",
        })

    # ============ 3. التنبؤ بالإيرادات ============
    pred = _predict_next_months()
    if pred["trend"] == "up":
        insights.append({
            "type": "success",
            "icon": "graph-up-arrow",
            "title": "اتجاه إيجابي",
            "message": f"الإيرادات في نمو ({pred['slope']:+,.0f} AED/شهر). "
                       f"توقع الشهر القادم: {pred['values'][0]:,.0f} AED.",
        })
    elif pred["trend"] == "down":
        insights.append({
            "type": "warning",
            "icon": "graph-down-arrow",
            "title": "تحذير: انخفاض متوقع",
            "message": f"الإيرادات تنخفض ({pred['slope']:,.0f} AED/شهر). "
                       f"يُنصح بتوسيع قاعدة العملاء أو إعادة التفاوض.",
        })

    # ============ 4. فواتير متأخرة ============
    risks = _get_risks()
    if risks["overdue_invoices"] > 0:
        insights.append({
            "type": "danger",
            "icon": "receipt-cutoff",
            "title": f"{risks['overdue_invoices']} فاتورة متأخرة",
            "message": f"إجمالي {risks['unpaid_total']:,.0f} AED لم تُسدد. "
                       f"تواصل مع العملاء أو أوقف الخدمات عن المتأخرين.",
        })

    # ============ 5. عقود تنتهي قريباً ============
    if risks["expiring_contracts"] > 0:
        insights.append({
            "type": "warning",
            "icon": "file-earmark-excel",
            "title": f"{risks['expiring_contracts']} عقد ينتهي خلال 30 يوم",
            "message": "ابدأ التفاوض على التجديد مبكراً قبل الانتهاء.",
        })

    # ============ 6. المهام المرتبطة بالشبك ============
    impound_missions = Mission.query.filter_by(is_impound=True).count()
    if impound_missions > 5:
        insights.append({
            "type": "info",
            "icon": "lock-fill",
            "title": f"{impound_missions} مهمة حجز بالشبك",
            "message": "راجع التكاليف المخزنة والإيرادات المتوقعة من هذه المهام.",
        })

    # ============ 7. معدل التحصيل ============
    total_revenue = float(db.session.query(
        func.coalesce(func.sum(Mission.revenue), 0)
    ).scalar() or 0)
    paid_missions = Mission.query.filter_by(customer_invoice_status="paid").all()
    paid_revenue = sum(m.revenue or 0 for m in paid_missions)
    collection_rate = _safe_div(paid_revenue, total_revenue) * 100

    if collection_rate < 50 and total_revenue > 0:
        insights.append({
            "type": "warning",
            "icon": "cash-coin",
            "title": f"معدل التحصيل: {collection_rate:.0f}%",
            "message": "أقل من 50% من الإيرادات محصّلة. "
                       "فعّل نظام تذكير آلي بالدفع.",
        })
    elif collection_rate >= 80:
        insights.append({
            "type": "success",
            "icon": "check-circle",
            "title": f"معدل تحصيل ممتاز: {collection_rate:.0f}%",
            "message": "أداء التحصيل ممتاز — حافظ على المستوى.",
        })

    # ============ 8. المعدة الأكثر استخداماً ============
    equipment = _get_equipment_stats()
    if equipment:
        top = equipment[0]
        insights.append({
            "type": "info",
            "icon": "truck",
            "title": f"أكثر معدة استخداماً: {top['name']}",
            "message": f"{top['count']} مهمة — إيراد {top['revenue']:,.0f} AED. "
                       f"تأكد من توفرها دائماً.",
        })

    # ============ 9. أفضل سائق ============
    drivers = _get_driver_performance(limit=1)
    if drivers:
        d = drivers[0]
        insights.append({
            "type": "success",
            "icon": "person-badge",
            "title": f"أفضل سائق: {d['name']}",
            "message": f"{d['missions']} مهمة بإيراد {d['revenue']:,.0f} AED. "
                       f"يمكن تكريمه أو ترقيته.",
        })

    return insights


# ============================================================
#  Health Score
# ============================================================
def _get_health_score():
    """
    حساب درجة الصحة العامة (0-100):
    - 40% الأداء المالي (الهامش + التحصيل)
    - 30% المخاطر (معكوسة)
    - 30% التشغيل (المهام المنجزة)
    """
    kpis = _get_financial_kpis()
    risks = _get_risks()

    # أداء مالي
    margin = kpis["total"]["margin"]
    financial_score = min(100, max(0, margin * 2.5))  # 40% هامش = 100 نقطة

    # معدل التحصيل
    total_revenue = kpis["total"]["revenue"] or 1
    paid = sum(
        m.revenue or 0 for m in Mission.query.filter_by(customer_invoice_status="paid").all()
    )
    collection = _safe_div(paid, total_revenue) * 100

    # المخاطر (معكوسة)
    risk_score = max(0, 100 - risks["total_score"])

    # التشغيل
    total_missions = Mission.query.count() or 1
    completed = Mission.query.filter(
        Mission.status.in_(["completed", "verified", "paid", "invoiced"])
    ).count()
    operational = _safe_div(completed, total_missions) * 100

    # المجموع المرجح
    overall = round(
        financial_score * 0.30 +
        collection * 0.15 +
        risk_score * 0.30 +
        operational * 0.25,
        1
    )

    if overall >= 80:
        level, color, emoji = "ممتاز", "success", "🌟"
    elif overall >= 60:
        level, color, emoji = "جيد", "info", "✅"
    elif overall >= 40:
        level, color, emoji = "متوسط", "warning", "⚠️"
    else:
        level, color, emoji = "ضعيف", "danger", "🔴"

    return {
        "overall": overall,
        "level": level,
        "color": color,
        "emoji": emoji,
        "financial": round(financial_score, 1),
        "collection": round(collection, 1),
        "risk": round(risk_score, 1),
        "operational": round(operational, 1),
    }


# ============================================================
#  Main Dashboard Route
# ============================================================
@bp.route("/")
@login_required
def index():
    kpis = _get_financial_kpis()
    monthly = _get_monthly_revenue(months_back=12)
    projects = _get_project_stats()
    equipment = _get_equipment_stats()
    payment = _get_payment_stats()
    suppliers = _get_supplier_performance(limit=5)
    drivers = _get_driver_performance(limit=5)
    risks = _get_risks()
    predictions = _predict_next_months()
    insights = _get_insights()
    health = _get_health_score()

    # آخر المهام
    recent_missions = Mission.query.order_by(
        Mission.mission_date.desc()
    ).limit(5).all()

    return render_template(
        "dashboard/index.html",
        kpis=kpis,
        monthly=monthly,
        projects=projects,
        equipment=equipment,
        payment=payment,
        suppliers=suppliers,
        drivers=drivers,
        risks=risks,
        predictions=predictions,
        insights=insights,
        health=health,
        recent_missions=recent_missions,
        now=datetime.utcnow(),
    )
# ============================================================
#  AI Analytics (المستشار الاستراتيجي الذكي - Deep Logic)
# ============================================================
@bp.route("/ai-analytics")
@login_required
def ai_analytics():
    from sqlalchemy import func
    from app.modules.suppliers.models import Supplier
    from app.modules.invoices.models import Invoice
    from app.modules.contracts.models import Contract
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    today = datetime.utcnow().date()
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # --- 1. تحليل الأداء المالي (Financial Trend Analysis) ---
    all_missions = Mission.query.all()
    total_revenue = sum(m.revenue or 0 for m in all_missions)
    total_cost = sum(m.cost or 0 for m in all_missions)
    total_profit = total_revenue - total_cost
    margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

    this_month_missions = [m for m in all_missions if m.mission_date and m.mission_date.date() >= this_month_start]
    last_month_missions = [m for m in all_missions if m.mission_date and last_month_start <= m.mission_date.date() <= last_month_end]

    this_month_rev = sum(m.revenue or 0 for m in this_month_missions)
    last_month_rev = sum(m.revenue or 0 for m in last_month_missions)
    
    rev_growth = 0
    if last_month_rev > 0:
        rev_growth = ((this_month_rev - last_month_rev) / last_month_rev) * 100

    # --- 2. كشف المخاطر المالية (Cashflow & Risk) ---
    overdue_invoices = Invoice.query.filter(
        Invoice.due_date.isnot(None), Invoice.due_date < today, Invoice.status != "paid"
    ).all()
    overdue_amount = sum(i.total_amount or 0 for i in overdue_invoices)

    # --- 3. تحليل أداء الموردين (Supplier Intelligence) ---
    supplier_stats = db.session.query(
        Supplier.company_name_ar,
        func.count(Mission.id).label('missions_count'),
        func.sum(Mission.revenue).label('revenue'),
        func.sum(Mission.cost).label('cost')
    ).join(Contract, Contract.supplier_id == Supplier.id)\
     .join(Mission, Mission.contract_id == Contract.id)\
     .group_by(Supplier.id).all()

    worst_supplier = None
    worst_margin = 100
    for s in supplier_stats:
        s_rev = float(s.revenue or 0)
        s_cost = float(s.cost or 0)
        if s_rev > 0:
            s_margin = ((s_rev - s_cost) / s_rev) * 100
            if s_margin < worst_margin and s.missions_count > 2:
                worst_margin = s_margin
                worst_supplier = s.company_name_ar

    # --- 4. بناء التوصيات الاستراتيجية (AI Insights) ---
    insights = []

    # تحليل النمو
    if rev_growth > 10:
        insights.append({"type": "success", "title": "نمو قوي", "text": f"الإيرادات نمت بنسبة {rev_growth:.1f}% مقارنة بالشهر الماضي. استمروا في هذا النهج."})
    elif rev_growth < -10:
        insights.append({"type": "danger", "title": "تراجع مقلق", "text": f"انخفاض بنسبة {abs(rev_growth):.1f}% في إيرادات هذا الشهر. يجب مراجعة استراتيجية جلب المهام."})

    # تحليل السيولة
    if overdue_amount > 0:
        insights.append({"type": "warning", "title": "نزيف نقدي", "text": f"يوجد مبلغ {overdue_amount:,.0f} درهم عالق في فواتير متأخرة. هذا المبلغ يمثل { (overdue_amount/total_revenue*100) if total_revenue > 0 else 0:.1f}% من إجمالي إيراداتك. فعّل قسم التحصيل فوراً."})

    # تحليل الموردين
    if worst_supplier:
        insights.append({"type": "danger", "title": "مورد يسبب خسارة", "text": f"المورد '{worst_supplier}' يعمل بهوامش ربح خطيرة ({worst_margin:.1f}%). نوصي بمراجعة أسعاره أو تقليل الاعتماد عليه."})

    # تحليل الكفاءة التشغيلية
    stuck_missions = Mission.query.filter(Mission.status == "in_progress", Mission.started_at < datetime.utcnow() - timedelta(hours=24)).count()
    if stuck_missions > 0:
        insights.append({"type": "info", "title": "اختناق تشغيلي", "text": f"يوجد {stuck_missions} مهمة تجاوزت 24 ساعة دون إنجاز. هذا يؤثر على رضا العملاء ويؤخر الفواتير."})

    # --- 5. التنبؤ المالي (Forecasting) ---
    avg_rev_3months = total_revenue / 3 if total_revenue > 0 else 0
    forecast = avg_rev_3months * 1.05 # افتراض نمو 5%
    
    if forecast > this_month_rev:
        insights.append({"type": "success", "title": "تنبؤ إيجابي", "text": f"بناءً على الأنماط الحالية، نتوقع أن تصل إيرادات الشهر القادم إلى {forecast:,.0f} درهم (بزيادة 5%)."})
    else:
        insights.append({"type": "warning", "title": "تنبؤ حذر", "text": f"النظام يتوقع تراجعاً طفيفاً في الإيرادات الشهر القادم إلى {forecast:,.0f} درهم ما لم يتم ضخ عقود جديدة."})


    # --- 6. الرسوم البيانية ---
    top_suppliers = sorted(supplier_stats, key=lambda x: x.revenue or 0, reverse=True)[:5]
    supplier_names = [s.company_name_ar for s in top_suppliers]
    supplier_revenues = [float(s.revenue or 0) for s in top_suppliers]

    health_score = min(100, max(0, int(margin * 2.5)))
    health_color = "#10b981" if health_score >= 80 else "#f59e0b" if health_score >= 50 else "#ef4444"

    return render_template(
        "dashboard/ai_analytics.html",
        total_revenue=total_revenue, total_profit=total_profit, margin=margin,
        insights=insights, supplier_names=supplier_names, supplier_revenues=supplier_revenues,
        health_score=health_score, health_color=health_color, missions_count=len(all_missions),
        rev_growth=rev_growth, overdue_amount=overdue_amount, forecast=forecast
    )