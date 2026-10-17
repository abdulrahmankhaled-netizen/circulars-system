"""مسارات العقود."""
from datetime import datetime, timedelta
from sqlalchemy import func
from app.modules.missions.models import Mission
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.core.permissions import require_permission
from app.core.workflow import WorkflowEngine, available_actions
from app.modules.contracts.models import Contract, ContractEquipment
from app.modules.contracts.forms import ContractForm
from app.modules.suppliers.models import Supplier
from app.modules.requests.models import EquipmentRequest

bp = Blueprint("contracts", __name__)


# ============================================================
#  Number Generator
# ============================================================
def generate_contract_number() -> str:
    """يولّد رقم عقد فريد: CON-2026-0001"""
    year = datetime.utcnow().year
    last = Contract.query.filter(
        Contract.contract_number.like(f"CON-{year}-%")
    ).order_by(Contract.id.desc()).first()
    if last:
        try:
            n = int(last.contract_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f"CON-{year}-{n:04d}"


# ============================================================
#  List
# ============================================================
@bp.route("/")
@login_required
@require_permission("contracts.view")
def list_contracts():
    status_filter = request.args.get("status", "").strip()
    supplier_filter = request.args.get("supplier", "").strip()
    q = request.args.get("q", "").strip()

    query = Contract.query

    if status_filter:
        query = query.filter(Contract.status == status_filter)
    if supplier_filter:
        try:
            query = query.filter(Contract.supplier_id == int(supplier_filter))
        except ValueError:
            pass
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Contract.contract_number.ilike(like),
                Contract.client_entity.ilike(like),
                Contract.region.ilike(like),
            )
        )

    contracts = query.order_by(Contract.created_at.desc()).all()

    # الإحصائيات
    from sqlalchemy import func
    total_value = db.session.query(
        func.coalesce(func.sum(Contract.value), 0)
    ).filter(Contract.status == "active").scalar()

    stats = {
        "total": Contract.query.count(),
        "active": Contract.query.filter_by(status="active").count(),
        "draft": Contract.query.filter_by(status="draft").count(),
        "pending_signature": Contract.query.filter_by(status="pending_signature").count(),
        "expiring": Contract.query.filter_by(status="expiring").count(),
        "total_value": float(total_value or 0),
    }

    suppliers = Supplier.query.filter_by(status="active")\
        .order_by(Supplier.company_name_ar).all()

    return render_template(
        "contracts/list.html",
        contracts=contracts,
        suppliers=suppliers,
        status_filter=status_filter,
        supplier_filter=supplier_filter,
        q=q,
        stats=stats,
    )


# ============================================================
#  Add (Manual)
# ============================================================
@bp.route("/add", methods=["GET", "POST"])
@login_required
@require_permission("contracts.create")
def add_contract():
    form = ContractForm()
    form.supplier_id.choices = [
        (s.id, s.company_name_ar)
        for s in Supplier.query.filter_by(status="active")
                                .order_by(Supplier.company_name_ar).all()
    ]

    # ⭐ تحميل أنواع الآليات
    equipment_choices = _get_equipment_choices()

    if request.method == "GET":
        form.contract_number.data = generate_contract_number()
        selected_equipment = []
    else:
        selected_equipment = _parse_equipment_from_form(request.form)

    if form.validate_on_submit():
        if Contract.query.filter_by(
            contract_number=form.contract_number.data.strip()
        ).first():
            flash("رقم العقد مستخدم مسبقاً", "danger")
            return render_template(
                "contracts/form.html",
                form=form, title="عقد جديد", contract=None,
                equipment_choices=equipment_choices,
                selected_equipment=selected_equipment,
            )

        c = Contract(
            contract_number=form.contract_number.data.strip(),
            supplier_id=form.supplier_id.data,
            client_entity=form.client_entity.data,
            client_entity_en=form.client_entity_en.data,
            region=form.region.data,
            region_en=form.region_en.data,
            location_keywords=form.location_keywords.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            value=form.value.data or 0.0,
            currency=form.currency.data,
            value_period=form.value_period.data,
            payment_terms=form.payment_terms.data,
            status=form.status.data,
            notes=form.notes.data,
        )

        if form.signed_document.data:
            from app.core.helpers import save_upload
            from flask import current_app
            path = save_upload(
                form.signed_document.data,
                f"contracts/{datetime.utcnow().strftime('%Y%m')}",
                current_app.config["UPLOAD_FOLDER"],
            )
            if path:
                c.signed_document = path
                c.signed_uploaded_at = datetime.utcnow()

        db.session.add(c)
        db.session.flush()

        # ⭐ حفظ المعدات
        for item in selected_equipment:
            ce = ContractEquipment(
                contract_id=c.id,
                equipment_key=item["key"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            db.session.add(ce)

        db.session.commit()
        flash(f"✅ تم إنشاء العقد {c.contract_number} ({len(selected_equipment)} آلية)", "success")
        return redirect(url_for("contracts.view_contract", cid=c.id))

    return render_template(
        "contracts/form.html",
        form=form,
        title="عقد جديد",
        contract=None,
        equipment_choices=equipment_choices,
        selected_equipment=selected_equipment,
    )
# ============================================================
#  Add from Request
# ============================================================
@bp.route("/from-request/<int:rid>", methods=["GET", "POST"])
@login_required
@require_permission("contracts.create")
def add_from_request(rid):
    """
    إنشاء عقد من طلب معتمد.
    """
    req = db.session.get(EquipmentRequest, rid)
    if not req:
        abort(404)

    if req.status != "approved":
        flash("لا يمكن إنشاء عقد إلا من طلب معتمد", "warning")
        return redirect(url_for("requests.view_request", rid=rid))

    form = ContractForm()
    form.supplier_id.choices = [
        (s.id, s.company_name_ar)
        for s in Supplier.query.filter_by(status="active")
                                .order_by(Supplier.company_name_ar).all()
    ]

    if request.method == "GET":
        # عبّئ الحقول من الطلب
        form.contract_number.data = generate_contract_number()
        form.client_entity.data = req.client_entity
        form.region.data = req.region
        form.start_date.data = req.needed_from
        form.end_date.data = req.needed_until
        form.status.data = "draft"
        # الحقول الإنجليزية تبقى فارغة — يملؤها المستخدم يدوياً

    if form.validate_on_submit():
        if Contract.query.filter_by(
            contract_number=form.contract_number.data.strip()
        ).first():
            flash("رقم العقد مستخدم مسبقاً", "danger")
            return render_template(
                "contracts/form.html", form=form,
                title="عقد جديد من طلب", contract=None, req=req
            )

        c = Contract(
            contract_number=form.contract_number.data.strip(),
            supplier_id=form.supplier_id.data,
            client_entity=form.client_entity.data,
            client_entity_en=form.client_entity_en.data,
            region=form.region.data,
            region_en=form.region_en.data,
            location_keywords=form.location_keywords.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            value=form.value.data or 0.0,
            currency=form.currency.data,
            value_period=form.value_period.data,
            payment_terms=form.payment_terms.data,
            status=form.status.data,
            notes=form.notes.data,
            source_request_id=req.id,
        )

        if form.signed_document.data:
            from app.core.helpers import save_upload
            from flask import current_app
            path = save_upload(
                form.signed_document.data,
                f"contracts/{datetime.utcnow().strftime('%Y%m')}",
                current_app.config["UPLOAD_FOLDER"],
            )
            if path:
                c.signed_document = path
                c.signed_uploaded_at = datetime.utcnow()

        db.session.add(c)
        db.session.flush()

        # نسخ بنود الطلب كمعدات العقد
        for item in req.items:
            ce = ContractEquipment(
                contract_id=c.id,
                equipment_key=item.equipment_key,
                quantity=item.quantity,
                unit_price=0.0,  # يُحدَّد لاحقاً في Rate Card
            )
            db.session.add(ce)

        # ربط الطلب بالعقد
        req.matched_contract_id = c.id
        req.contracted_at = datetime.utcnow()

        db.session.commit()
        flash(f"✅ تم إنشاء العقد {c.contract_number} من الطلب", "success")
        return redirect(url_for("contracts.view_contract", cid=c.id))

    return render_template(
        "contracts/form.html",
        form=form,
        title="عقد جديد من طلب",
        contract=None,
        req=req,
    )


# ============================================================
#  Edit
# ============================================================
@bp.route("/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("contracts.edit")
def edit_contract(cid):
    c = db.session.get(Contract, cid)
    if not c:
        abort(404)

    form = ContractForm(obj=c)
    form.supplier_id.choices = [
        (s.id, s.company_name_ar)
        for s in Supplier.query.order_by(Supplier.company_name_ar).all()
    ]

    # ⭐ تحميل أنواع الآليات
    equipment_choices = _get_equipment_choices()

    # ⭐ قراءة المعدات
    if request.method == "POST":
        selected_equipment = _parse_equipment_from_form(request.form)
    else:
        selected_equipment = [
            {
                "key": item.equipment_key,
                "quantity": item.quantity or 1,
                "unit_price": item.unit_price or 0.0,
            }
            for item in c.equipment_items
        ]

    if form.validate_on_submit():
        existing = Contract.query.filter_by(
            contract_number=form.contract_number.data.strip()
        ).first()
        if existing and existing.id != c.id:
            flash("رقم العقد مستخدم مسبقاً", "danger")
            return render_template(
                "contracts/form.html",
                form=form, title=f"تعديل: {c.contract_number}",
                contract=c, equipment_choices=equipment_choices,
                selected_equipment=selected_equipment,
            )

        c.contract_number = form.contract_number.data.strip()
        c.supplier_id = form.supplier_id.data
        c.client_entity = form.client_entity.data
        c.client_entity_en = form.client_entity_en.data
        c.region = form.region.data
        c.region_en = form.region_en.data
        c.location_keywords = form.location_keywords.data
        c.start_date = form.start_date.data
        c.end_date = form.end_date.data
        c.value = form.value.data or 0.0
        c.currency = form.currency.data
        c.value_period = form.value_period.data
        c.payment_terms = form.payment_terms.data
        c.status = form.status.data
        c.notes = form.notes.data

        if form.signed_document.data:
            from app.core.helpers import save_upload
            from flask import current_app
            path = save_upload(
                form.signed_document.data,
                f"contracts/{datetime.utcnow().strftime('%Y%m')}",
                current_app.config["UPLOAD_FOLDER"],
            )
            if path:
                c.signed_document = path
                c.signed_uploaded_at = datetime.utcnow()

        # ⭐ تحديث المعدات (احذف ثم أعد الإضافة)
        for old_item in c.equipment_items:
            db.session.delete(old_item)
        db.session.flush()

        for item in selected_equipment:
            ce = ContractEquipment(
                contract_id=c.id,
                equipment_key=item["key"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            db.session.add(ce)

        db.session.commit()
        flash(f"✅ تم تحديث العقد ({len(selected_equipment)} آلية)", "success")
        return redirect(url_for("contracts.view_contract", cid=c.id))

    return render_template(
        "contracts/form.html",
        form=form,
        title=f"تعديل: {c.contract_number}",
        contract=c,
        equipment_choices=equipment_choices,
        selected_equipment=selected_equipment,
    )
# ============================================================
#  View
# ============================================================
@bp.route("/<int:cid>")
@login_required
@require_permission("contracts.view")
def view_contract(cid):
    c = db.session.get(Contract, cid)
    if not c:
        abort(404)

    # الأزرار المتاحة من الـ workflow
    actions = available_actions("contract", c.status, current_user)

    # سجل التغييرات
    from app.modules.workflow.models import WorkflowLog
    logs = WorkflowLog.query.filter_by(
        entity_type="contract", entity_id=c.id
    ).order_by(WorkflowLog.created_at.asc()).all()

    # الطلبات المرتبطة بهذا العقد
    linked_requests = EquipmentRequest.query.filter_by(
        matched_contract_id=c.id
    ).all()

    return render_template(
        "contracts/view.html",
        contract=c,
        actions=actions,
        logs=logs,
        linked_requests=linked_requests,
    )


# ============================================================
#  Workflow Actions
# ============================================================
def _execute_action(c, action, comment=""):
    engine = WorkflowEngine("contract")
    ok, err = engine.execute(c, action, user=current_user, comment=comment)
    if ok:
        db.session.commit()
    return ok, err


@bp.route("/<int:cid>/action", methods=["POST"])
@login_required
@require_permission("contracts.edit")
def action_contract(cid):
    c = db.session.get(Contract, cid)
    if not c:
        abort(404)

    action = request.form.get("action", "").strip()
    comment = request.form.get("comment", "").strip()

    if not action:
        flash("لم يتم تحديد إجراء", "danger")
        return redirect(url_for("contracts.view_contract", cid=cid))

    ok, err = _execute_action(c, action, comment)
    if ok:
        flash(f"✅ تم تنفيذ '{action}' بنجاح", "success")
    else:
        flash(f"❌ {err}", "danger")
    return redirect(url_for("contracts.view_contract", cid=cid))


# ============================================================
#  Delete
# ============================================================
@bp.route("/<int:cid>/delete", methods=["POST"])
@login_required
@require_permission("contracts.delete")
def delete_contract(cid):
    c = db.session.get(Contract, cid)
    if not c:
        abort(404)

    if c.status == "active" and not current_user.is_admin:
        flash("لا يمكن حذف عقد نشط — يجب إلغاؤه أولاً", "warning")
        return redirect(url_for("contracts.view_contract", cid=cid))

    # فك ربط الطلبات
    EquipmentRequest.query.filter_by(matched_contract_id=c.id)\
        .update({"matched_contract_id": None})

    number = c.contract_number
    db.session.delete(c)
    db.session.commit()
    flash(f"🗑️ تم حذف العقد {number}", "warning")
    return redirect(url_for("contracts.list_contracts"))


# ============================================================
#  Print Contract
# ============================================================
@bp.route("/<int:cid>/print")
@login_required
@require_permission("contracts.view")
def print_contract(cid):
    """صفحة طباعة العقد (A4)."""
    c = db.session.get(Contract, cid)
    if not c:
        abort(404)

    auto_print = request.args.get("auto") == "1"

    return render_template(
        "contracts/print.html",
        contract=c,
        auto_print=auto_print,
    )


# ============================================================
#  PDF — يفتح صفحة الطباعة مع hint للمستخدم
# ============================================================
@bp.route("/<int:cid>/pdf")
@login_required
@require_permission("contracts.view")
def contract_pdf(cid):
    """
    يفتح صفحة الطباعة مع تنبيه للمستخدم باستخدام
    خاصية "Save as PDF" في المتصفح.
    """
    return redirect(url_for("contracts.print_contract", cid=cid, pdf_hint="1"))


# ============================================================
#  Helpers
# ============================================================
def _get_equipment_choices():
    """يجلب قائمة أنواع الآليات من قاعدة البيانات أو من constants."""
    equipment_choices = []

    try:
        from app.modules.equipment.models import EquipmentType
        types = EquipmentType.query.filter_by(is_active=True)\
            .order_by(EquipmentType.sort_order, EquipmentType.name_ar).all()
        equipment_choices = [
            (t.key, f"{t.name_ar} ({t.name_en or ''})".strip())
            for t in types
        ]
    except Exception as e:
        print(f"[Equipment] Error loading types: {e}")

    # Fallback — إذا لم توجد أنواع في قاعدة البيانات
    if not equipment_choices:
        try:
            from app.core.constants import EQUIPMENT_TYPES
            equipment_choices = [
                (eq["key"], eq["name_ar"]) for eq in EQUIPMENT_TYPES
            ]
        except Exception as e:
            print(f"[Equipment] Error loading constants: {e}")

    return equipment_choices


def _parse_equipment_from_form(form_data):
    """يقرأ صفوف المعدات من request.form."""
    keys = form_data.getlist("equipment_key[]")
    qtys = form_data.getlist("equipment_qty[]")
    prices = form_data.getlist("equipment_price[]")

    result = []
    for i, key in enumerate(keys):
        if not key or not key.strip():
            continue

        qty = 1
        price = 0.0

        try:
            if i < len(qtys):
                qty = int(qtys[i]) or 1
        except (ValueError, TypeError):
            qty = 1

        try:
            if i < len(prices):
                price = float(prices[i]) or 0.0
        except (ValueError, TypeError):
            price = 0.0

        result.append({
            "key": key.strip(),
            "quantity": qty,
            "unit_price": price,
        })
# ==================================================================
#  Contract Comparison
# ==================================================================
def _period_dates(period_type, from_str="", to_str=""):
    """يحسب تواريخ البداية والنهاية حسب نوع الفترة."""
    today = datetime.utcnow().date()
    
    if period_type == "this_month":
        return today.replace(day=1), today
    elif period_type == "last_month":
        first = today.replace(day=1)
        last = first - timedelta(days=1)
        return last.replace(day=1), last
    elif period_type == "last_30":
        return today - timedelta(days=30), today
    elif period_type == "last_7":
        return today - timedelta(days=7), today
    elif period_type == "this_year":
        return today.replace(month=1, day=1), today
    elif period_type == "last_year":
        return today.replace(year=today.year-1, month=1, day=1), \
               today.replace(year=today.year-1, month=12, day=31)
    elif period_type == "custom" and from_str and to_str:
        try:
            return (datetime.strptime(from_str, "%Y-%m-%d").date(),
                    datetime.strptime(to_str, "%Y-%m-%d").date())
        except ValueError:
            return today.replace(day=1), today
    else:
        return today.replace(day=1), today


def _aggregate_missions(contract_id, from_date, to_date):
    """يجمع إحصائيات المهام لعقد في فترة زمنية."""
    from collections import defaultdict
    
    missions = Mission.query.filter(
        Mission.contract_id == contract_id,
        func.date(Mission.mission_date) >= from_date.isoformat(),
        func.date(Mission.mission_date) <= to_date.isoformat(),
    ).all()
    
    total_revenue = sum(m.revenue or 0 for m in missions)
    total_cost = sum(m.cost or 0 for m in missions)
    profit = total_revenue - total_cost
    margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
    
    by_equipment = defaultdict(lambda: {"count": 0, "revenue": 0, "cost": 0})
    for m in missions:
        key = m.equipment_name_ar()
        by_equipment[key]["count"] += 1
        by_equipment[key]["revenue"] += (m.revenue or 0)
        by_equipment[key]["cost"] += (m.cost or 0)
    
    payment = {"paid": 0, "pending": 0, "cancelled": 0}
    for m in missions:
        sp = m.supplier_payment_status or "pending"
        if sp in payment:
            payment[sp] += 1
    
    by_driver = defaultdict(lambda: {"count": 0, "revenue": 0})
    for m in missions:
        if m.driver_name:
            key = m.driver_name.split("(")[0].strip()
            by_driver[key]["count"] += 1
            by_driver[key]["revenue"] += (m.revenue or 0)
    drivers = sorted(
        [{"name": k, "count": v["count"], "revenue": v["revenue"]} for k, v in by_driver.items()],
        key=lambda x: x["count"], reverse=True
    )[:5]
    
    return {
        "missions": missions,
        "count": len(missions),
        "revenue": total_revenue,
        "cost": total_cost,
        "profit": profit,
        "margin": round(margin, 1),
        "avg_per_mission": round(total_revenue / len(missions), 2) if missions else 0,
        "by_equipment": dict(by_equipment),
        "payment": payment,
        "drivers": drivers,
        "completed": sum(1 for m in missions if m.status in ("completed", "verified", "paid")),
        "in_progress": sum(1 for m in missions if m.status == "in_progress"),
    }


def _calc_diff(current, previous):
    """يحسب الفرق والنسبة المئوية."""
    diff = current - previous
    if previous == 0:
        pct = 100 if current > 0 else 0
    else:
        pct = (diff / abs(previous)) * 100
    return {
        "diff": round(diff, 2),
        "pct": round(pct, 1),
        "direction": "up" if diff > 0.01 else ("down" if diff < -0.01 else "flat"),
        "color": "success" if diff >= 0 else "danger",
    }


@bp.route("/<int:cid>/compare")
@login_required
@require_permission("contracts.view")
def compare_contract(cid):
    """مقارنة عقد بين فترتين."""
    c = db.session.get(Contract, cid)
    if not c:
        abort(404)
    
    p1_type = request.args.get("p1", "this_month")
    p1_from_str = request.args.get("p1_from", "")
    p1_to_str = request.args.get("p1_to", "")
    p1_from, p1_to = _period_dates(p1_type, p1_from_str, p1_to_str)
    
    p2_type = request.args.get("p2", "last_month")
    p2_from_str = request.args.get("p2_from", "")
    p2_to_str = request.args.get("p2_to", "")
    p2_from, p2_to = _period_dates(p2_type, p2_from_str, p2_to_str)
    
    p1 = _aggregate_missions(cid, p1_from, p1_to)
    p2 = _aggregate_missions(cid, p2_from, p2_to)
    
    diffs = {
        "missions": _calc_diff(p1["count"], p2["count"]),
        "revenue": _calc_diff(p1["revenue"], p2["revenue"]),
        "cost": _calc_diff(p1["cost"], p2["cost"]),
        "profit": _calc_diff(p1["profit"], p2["profit"]),
        "margin": _calc_diff(p1["margin"], p2["margin"]),
        "avg_per_mission": _calc_diff(p1["avg_per_mission"], p2["avg_per_mission"]),
        "completed": _calc_diff(p1["completed"], p2["completed"]),
    }
    
    all_equipment = set(p1["by_equipment"].keys()) | set(p2["by_equipment"].keys())
    equipment_comparison = []
    for eq in sorted(all_equipment):
        e1 = p1["by_equipment"].get(eq, {"count": 0, "revenue": 0, "cost": 0})
        e2 = p2["by_equipment"].get(eq, {"count": 0, "revenue": 0, "cost": 0})
        equipment_comparison.append({
            "name": eq,
            "count1": e1["count"],
            "count2": e2["count"],
            "count_diff": e1["count"] - e2["count"],
            "revenue1": e1["revenue"],
            "revenue2": e2["revenue"],
            "revenue_diff": e1["revenue"] - e2["revenue"],
        })
    equipment_comparison.sort(key=lambda x: abs(x["count_diff"]), reverse=True)
    
    # التوصيات الذكية
    insights = []
    if diffs["missions"]["direction"] == "up":
        insights.append({
            "type": "success",
            "icon": "graph-up-arrow",
            "text": f"المهام زادت بنسبة {abs(diffs['missions']['pct'])}% عن الفترة السابقة",
        })
    elif diffs["missions"]["direction"] == "down":
        insights.append({
            "type": "warning",
            "icon": "graph-down-arrow",
            "text": f"⚠️ المهام انخفضت بنسبة {abs(diffs['missions']['pct'])}% — راجع الأداء",
        })
    
    if diffs["profit"]["direction"] == "up" and diffs["profit"]["diff"] > 0:
        insights.append({
            "type": "success",
            "icon": "cash-coin",
            "text": f"الربح ارتفع بمقدار {diffs['profit']['diff']:,.0f} AED",
        })
    elif diffs["profit"]["direction"] == "down" and diffs["profit"]["diff"] < 0:
        insights.append({
            "type": "danger",
            "icon": "cash-stack",
            "text": f"⚠️ الربح انخفض بمقدار {abs(diffs['profit']['diff']):,.0f} AED",
        })
    
    if p1["count"] > 0:
        insights.append({
            "type": "info",
            "icon": "bar-chart",
            "text": f"متوسط الإيراد لكل مهمة: {p1['avg_per_mission']:,.0f} AED",
        })
    
    return render_template(
        "contracts/compare.html",
        contract=c,
        p1=p1, p2=p2,
        p1_from=p1_from.strftime("%Y-%m-%d"),
        p1_to=p1_to.strftime("%Y-%m-%d"),
        p2_from=p2_from.strftime("%Y-%m-%d"),
        p2_to=p2_to.strftime("%Y-%m-%d"),
        p1_type=p1_type, p2_type=p2_type,
        diffs=diffs,
        equipment_comparison=equipment_comparison,
        insights=insights,
    )


@bp.route("/compare-all")
@login_required
@require_permission("contracts.view")
def compare_all_contracts():
    """مقارنة جميع العقود بين فترتين."""
    p1_type = request.args.get("p1", "this_month")
    p2_type = request.args.get("p2", "last_month")
    p1_from, p1_to = _period_dates(p1_type)
    p2_from, p2_to = _period_dates(p2_type)
    
    contracts = Contract.query.order_by(Contract.contract_number).all()
    
    results = []
    totals = {
        "p1_missions": 0, "p1_revenue": 0, "p1_profit": 0,
        "p2_missions": 0, "p2_revenue": 0, "p2_profit": 0,
    }
    
    for c in contracts:
        p1 = _aggregate_missions(c.id, p1_from, p1_to)
        p2 = _aggregate_missions(c.id, p2_from, p2_to)
        
        if p1["count"] == 0 and p2["count"] == 0:
            continue
        
        totals["p1_missions"] += p1["count"]
        totals["p1_revenue"] += p1["revenue"]
        totals["p1_profit"] += p1["profit"]
        totals["p2_missions"] += p2["count"]
        totals["p2_revenue"] += p2["revenue"]
        totals["p2_profit"] += p2["profit"]
        
        results.append({
            "contract": c,
            "p1": p1,
            "p2": p2,
            "missions_diff": p1["count"] - p2["count"],
            "revenue_diff": p1["revenue"] - p2["revenue"],
            "profit_diff": p1["profit"] - p2["profit"],
        })
    
    results.sort(key=lambda x: abs(x["revenue_diff"]), reverse=True)
    
    grand_diffs = {
        "missions": _calc_diff(totals["p1_missions"], totals["p2_missions"]),
        "revenue": _calc_diff(totals["p1_revenue"], totals["p2_revenue"]),
        "profit": _calc_diff(totals["p1_profit"], totals["p2_profit"]),
    }
    
    return render_template(
        "contracts/compare_all.html",
        results=results,
        totals=totals,
        grand_diffs=grand_diffs,
        p1_from=p1_from.strftime("%Y-%m-%d"),
        p1_to=p1_to.strftime("%Y-%m-%d"),
        p2_from=p2_from.strftime("%Y-%m-%d"),
        p2_to=p2_to.strftime("%Y-%m-%d"),
        p1_type=p1_type,
        p2_type=p2_type,
    )

    return result