"""مسارات العقود."""
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, current_app
)
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.core.permissions import require_permission
from app.core.workflow import WorkflowEngine, available_actions
from app.modules.contracts.models import Contract, ContractEquipment
from app.modules.contracts.forms import ContractForm
from app.modules.suppliers.models import Supplier
from app.modules.requests.models import EquipmentRequest
from app.modules.missions.models import Mission

bp = Blueprint("contracts", __name__)


# ============================================================
#  Helpers
# ============================================================
def generate_contract_number() -> str:
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


def _get_equipment_choices():
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

    if not equipment_choices:
        from app.core.constants import EQUIPMENT_TYPES
        equipment_choices = [
            (eq["key"], eq["name_ar"]) for eq in EQUIPMENT_TYPES
        ]
    return equipment_choices


def _parse_equipment_from_form(form_data):
    keys = form_data.getlist("equipment_key[]")
    qtys = form_data.getlist("equipment_qty[]")
    prices = form_data.getlist("equipment_price[]")
    periods = form_data.getlist("equipment_period[]")

    result = []
    for i, key in enumerate(keys):
        if not key or not key.strip():
            continue
        qty = 1
        price = 0.0
        period = "per_mission"
        try:
            if i < len(qtys) and qtys[i]: qty = int(qtys[i]) or 1
        except (ValueError, TypeError): qty = 1
        try:
            if i < len(prices) and prices[i]: price = float(prices[i]) or 0.0
        except (ValueError, TypeError): price = 0.0
        try:
            if i < len(periods) and periods[i]: period = str(periods[i]).strip()
        except (ValueError, TypeError): period = "per_mission"

        result.append({
            "key": key.strip(),
            "quantity": qty,
            "unit_price": price,
            "pricing_period": period,
        })
    return result


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
    if status_filter: query = query.filter(Contract.status == status_filter)
    if supplier_filter:
        try: query = query.filter(Contract.supplier_id == int(supplier_filter))
        except ValueError: pass
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Contract.contract_number.ilike(like),
            Contract.project_name.ilike(like),
            Contract.client_entity.ilike(like),
            Contract.region.ilike(like),
        ))

    contracts = query.order_by(Contract.created_at.desc()).all()
    all_contracts = Contract.query.all()
    total_all_value = sum(c.calculated_value for c in all_contracts)
    total_equipments = sum(sum(item.quantity or 1 for item in c.equipment_items) for c in all_contracts)

    stats = {
        "total": Contract.query.count(),
        "active": Contract.query.filter_by(status="active").count(),
        "draft": Contract.query.filter_by(status="draft").count(),
        "pending_signature": Contract.query.filter_by(status="pending_signature").count(),
        "expiring": Contract.query.filter_by(status="expiring").count(),
        "total_value": float(total_all_value),
        "total_equipments": int(total_equipments),
    }
    suppliers = Supplier.query.filter_by(status="active").order_by(Supplier.company_name_ar).all()

    return render_template("contracts/list.html", contracts=contracts, suppliers=suppliers,
                           status_filter=status_filter, supplier_filter=supplier_filter, q=q, stats=stats)


# ============================================================
#  Add (Manual)
# ============================================================
@bp.route("/add", methods=["GET", "POST"])
@login_required
@require_permission("contracts.create")
def add_contract():
    form = ContractForm()
    form.supplier_id.choices = [(s.id, s.company_name_ar) for s in Supplier.query.filter_by(status="active").order_by(Supplier.company_name_ar).all()]
    equipment_choices = _get_equipment_choices()

    if request.method == "GET":
        form.contract_number.data = generate_contract_number()
        selected_equipment = []
    else:
        selected_equipment = _parse_equipment_from_form(request.form)

    if form.validate_on_submit():
        if Contract.query.filter_by(contract_number=form.contract_number.data.strip()).first():
            flash("رقم العقد مستخدم مسبقاً", "danger")
            return render_template("contracts/form.html", form=form, title="عقد جديد", contract=None, equipment_choices=equipment_choices, selected_equipment=selected_equipment)

        total_value = sum(item["quantity"] * item["unit_price"] for item in selected_equipment) if selected_equipment else 0

        c = Contract(
            contract_number=form.contract_number.data.strip(),
            project_name=form.project_name.data, # ⭐ حفظ اسم المشروع
            supplier_id=form.supplier_id.data,
            client_entity=form.client_entity.data,
            client_entity_en=form.client_entity_en.data,
            region=form.region.data,
            region_en=form.region_en.data,
            location_keywords=form.location_keywords.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            value=total_value,
            currency=form.currency.data,
            value_period=form.value_period.data,
            payment_terms=form.payment_terms.data,
            status=form.status.data,
            notes=form.notes.data,
            term_duration=form.term_duration.data,
            response_time_dubai=form.response_time_dubai.data or 30,
            response_time_other=form.response_time_other.data or 60,
            notice_days=form.notice_days.data or 30,
            payment_days=form.payment_days.data or 30,
            penalty_late=form.penalty_late.data or 100.0,
            penalty_late_mins=form.penalty_late_mins.data or 30,
            penalty_noshow=form.penalty_noshow.data or 500.0,
            penalty_unlisted=form.penalty_unlisted.data or 500.0,
            penalty_article5=form.penalty_article5.data or 5000.0,
            penalty_docs=form.penalty_docs.data or 100.0,
            penalty_max_percent=form.penalty_max_percent.data or 20,
            penalty_max_times=form.penalty_max_times.data or 3,
            penalty_max_months=form.penalty_max_months.data or 6,
            insurance_liability_aed=form.insurance_liability_aed.data or 1000000.0,
            insurance_goods_aed=form.insurance_goods_aed.data or 500000.0,
            compensation_days=form.compensation_days.data or 7,
            incident_report_hours=form.incident_report_hours.data or 24,
            invoice_submit_days=form.invoice_submit_days.data or 5,
            invoice_review_days=form.invoice_review_days.data or 7,
            cure_days=form.cure_days.data or 15,
            handover_hours=form.handover_hours.data or 24,
            liability_months=form.liability_months.data or 6,
            confidentiality_years=form.confidentiality_years.data or 5,
            force_majeure_hours=form.force_majeure_hours.data or 48,
            equipment_age_years=form.equipment_age_years.data or 5,
            doc_upload_hours=form.doc_upload_hours.data or 2,
            lead_time_days=form.lead_time_days.data or 14,
            company_coordinator=form.company_coordinator.data,
            company_phone=form.company_phone.data,
            company_email=form.company_email.data,
        )

        if form.signed_document.data:
            from app.core.helpers import save_upload
            path = save_upload(form.signed_document.data, f"contracts/{datetime.utcnow().strftime('%Y%m')}", current_app.config["UPLOAD_FOLDER"])
            if path: c.signed_document = path; c.signed_uploaded_at = datetime.utcnow()

        db.session.add(c)
        db.session.commit()

        for item in selected_equipment or []:
            db.session.add(ContractEquipment(contract_id=c.id, equipment_key=item["key"], quantity=item["quantity"], unit_price=item["unit_price"], pricing_period=item.get("pricing_period", "per_mission")))

        db.session.commit()
        flash(f"✅ تم إنشاء العقد {c.contract_number} ({len(selected_equipment or [])} آلية)", "success")
        return redirect(url_for("contracts.view_contract", cid=c.id))

    return render_template("contracts/form.html", form=form, title="عقد جديد", contract=None, equipment_choices=equipment_choices, selected_equipment=selected_equipment)


# ============================================================
#  Add from Request
# ============================================================
@bp.route("/from-request/<int:rid>", methods=["GET", "POST"])
@login_required
@require_permission("contracts.create")
def add_from_request(rid):
    req = db.session.get(EquipmentRequest, rid)
    if not req: abort(404)
    if req.status != "approved":
        flash("لا يمكن إنشاء عقد إلا من طلب معتمد", "warning")
        return redirect(url_for("requests.view_request", rid=rid))

    form = ContractForm()
    form.supplier_id.choices = [(s.id, s.company_name_ar) for s in Supplier.query.filter_by(status="active").order_by(Supplier.company_name_ar).all()]

    if request.method == "GET":
        form.contract_number.data = generate_contract_number()
        form.project_name.data = req.title
        form.client_entity.data = req.client_entity
        form.region.data = req.region
        form.start_date.data = req.needed_from
        form.end_date.data = req.needed_until
        form.status.data = "draft"

    if form.validate_on_submit():
        if Contract.query.filter_by(contract_number=form.contract_number.data.strip()).first():
            flash("رقم العقد مستخدم مسبقاً", "danger")
            return render_template("contracts/form.html", form=form, title="عقد جديد من طلب", contract=None, req=req)

        c = Contract(
            contract_number=form.contract_number.data.strip(),
            project_name=form.project_name.data, # ⭐
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
            term_duration=form.term_duration.data,
            response_time_dubai=form.response_time_dubai.data or 30,
            response_time_other=form.response_time_other.data or 60,
            notice_days=form.notice_days.data or 30,
            payment_days=form.payment_days.data or 30,
            penalty_late=form.penalty_late.data or 100.0,
            penalty_late_mins=form.penalty_late_mins.data or 30,
            penalty_noshow=form.penalty_noshow.data or 500.0,
            penalty_unlisted=form.penalty_unlisted.data or 500.0,
            penalty_article5=form.penalty_article5.data or 5000.0,
            penalty_docs=form.penalty_docs.data or 100.0,
            penalty_max_percent=form.penalty_max_percent.data or 20,
            penalty_max_times=form.penalty_max_times.data or 3,
            penalty_max_months=form.penalty_max_months.data or 6,
            insurance_liability_aed=form.insurance_liability_aed.data or 1000000.0,
            insurance_goods_aed=form.insurance_goods_aed.data or 500000.0,
            compensation_days=form.compensation_days.data or 7,
            incident_report_hours=form.incident_report_hours.data or 24,
            invoice_submit_days=form.invoice_submit_days.data or 5,
            invoice_review_days=form.invoice_review_days.data or 7,
            cure_days=form.cure_days.data or 15,
            handover_hours=form.handover_hours.data or 24,
            liability_months=form.liability_months.data or 6,
            confidentiality_years=form.confidentiality_years.data or 5,
            force_majeure_hours=form.force_majeure_hours.data or 48,
            equipment_age_years=form.equipment_age_years.data or 5,
            doc_upload_hours=form.doc_upload_hours.data or 2,
            lead_time_days=form.lead_time_days.data or 14,
            company_coordinator=form.company_coordinator.data,
            company_phone=form.company_phone.data,
            company_email=form.company_email.data,
        )

        if form.signed_document.data:
            from app.core.helpers import save_upload
            path = save_upload(form.signed_document.data, f"contracts/{datetime.utcnow().strftime('%Y%m')}", current_app.config["UPLOAD_FOLDER"])
            if path: c.signed_document = path; c.signed_uploaded_at = datetime.utcnow()

        db.session.add(c)
        db.session.commit() 

        for item in req.items:
            db.session.add(ContractEquipment(contract_id=c.id, equipment_key=item.equipment_key, quantity=item.quantity, unit_price=0.0, pricing_period="per_mission"))

        req.matched_contract_id = c.id
        req.contracted_at = datetime.utcnow()

        db.session.commit()
        flash(f"✅ تم إنشاء العقد {c.contract_number} من الطلب", "success")
        return redirect(url_for("contracts.view_contract", cid=c.id))

    return render_template("contracts/form.html", form=form, title="عقد جديد من طلب", contract=None, req=req, equipment_choices=_get_equipment_choices(), selected_equipment=[])


# ============================================================
#  Edit
# ============================================================
@bp.route("/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("contracts.edit")
def edit_contract(cid):
    c = db.session.get(Contract, cid)
    if not c: abort(404)

    form = ContractForm(obj=c)
    form.supplier_id.choices = [(s.id, s.company_name_ar) for s in Supplier.query.order_by(Supplier.company_name_ar).all()]
    equipment_choices = _get_equipment_choices()

    if request.method == "POST":
        selected_equipment = _parse_equipment_from_form(request.form)
    else:
        selected_equipment = [{"key": item.equipment_key, "quantity": item.quantity or 1, "unit_price": item.unit_price or 0.0, "pricing_period": item.pricing_period or "per_mission"} for item in c.equipment_items]

    if form.validate_on_submit():
        existing = Contract.query.filter_by(contract_number=form.contract_number.data.strip()).first()
        if existing and existing.id != c.id:
            flash("رقم العقد مستخدم مسبقاً", "danger")
            return render_template("contracts/form.html", form=form, title=f"تعديل: {c.contract_number}", contract=c, equipment_choices=equipment_choices, selected_equipment=selected_equipment)

        c.contract_number = form.contract_number.data.strip()
        c.project_name = form.project_name.data # ⭐ حفظ اسم المشروع
        c.supplier_id = form.supplier_id.data
        c.client_entity = form.client_entity.data
        c.client_entity_en = form.client_entity_en.data
        c.region = form.region.data
        c.region_en = form.region_en.data
        c.location_keywords = form.location_keywords.data
        c.start_date = form.start_date.data
        c.end_date = form.end_date.data
        c.currency = form.currency.data
        c.value_period = form.value_period.data
        c.payment_terms = form.payment_terms.data
        c.status = form.status.data
        c.notes = form.notes.data
        c.term_duration = form.term_duration.data
        c.response_time_dubai = form.response_time_dubai.data
        c.response_time_other = form.response_time_other.data
        c.notice_days = form.notice_days.data
        c.payment_days = form.payment_days.data
        c.penalty_late = form.penalty_late.data
        c.penalty_late_mins = form.penalty_late_mins.data
        c.penalty_noshow = form.penalty_noshow.data
        c.penalty_unlisted = form.penalty_unlisted.data
        c.penalty_article5 = form.penalty_article5.data
        c.penalty_docs = form.penalty_docs.data
        c.penalty_max_percent = form.penalty_max_percent.data
        c.penalty_max_times = form.penalty_max_times.data
        c.penalty_max_months = form.penalty_max_months.data
        c.insurance_liability_aed = form.insurance_liability_aed.data
        c.insurance_goods_aed = form.insurance_goods_aed.data
        c.compensation_days = form.compensation_days.data
        c.incident_report_hours = form.incident_report_hours.data
        c.invoice_submit_days = form.invoice_submit_days.data
        c.invoice_review_days = form.invoice_review_days.data
        c.cure_days = form.cure_days.data
        c.handover_hours = form.handover_hours.data
        c.liability_months = form.liability_months.data
        c.confidentiality_years = form.confidentiality_years.data
        c.force_majeure_hours = form.force_majeure_hours.data
        c.equipment_age_years = form.equipment_age_years.data
        c.doc_upload_hours = form.doc_upload_hours.data
        c.lead_time_days = form.lead_time_days.data
        c.company_coordinator = form.company_coordinator.data
        c.company_phone = form.company_phone.data
        c.company_email = form.company_email.data

        if form.signed_document.data:
            from app.core.helpers import save_upload
            path = save_upload(form.signed_document.data, f"contracts/{datetime.utcnow().strftime('%Y%m')}", current_app.config["UPLOAD_FOLDER"])
            if path: c.signed_document = path; c.signed_uploaded_at = datetime.utcnow()

        for old_item in c.equipment_items:
            db.session.delete(old_item)
        db.session.flush()

        total_value = 0
        for item in selected_equipment:
            total_value += (item["quantity"] * item["unit_price"])
            db.session.add(ContractEquipment(contract_id=c.id, equipment_key=item["key"], quantity=item["quantity"], unit_price=item["unit_price"], pricing_period=item.get("pricing_period", "per_mission")))

        c.value = total_value
        db.session.commit()
        flash(f"✅ تم تحديث العقد ({len(selected_equipment)} آلية)", "success")
        return redirect(url_for("contracts.view_contract", cid=c.id))

    return render_template("contracts/form.html", form=form, title=f"تعديل: {c.contract_number}", contract=c, equipment_choices=equipment_choices, selected_equipment=selected_equipment)


# ============================================================
#  View
# ============================================================
@bp.route("/<int:cid>")
@login_required
@require_permission("contracts.view")
def view_contract(cid):
    c = db.session.get(Contract, cid)
    if not c: abort(404)
    actions = available_actions("contract", c.status, current_user)
    from app.modules.workflow.models import WorkflowLog
    logs = WorkflowLog.query.filter_by(entity_type="contract", entity_id=c.id).order_by(WorkflowLog.created_at.asc()).all()
    linked_requests = EquipmentRequest.query.filter_by(matched_contract_id=c.id).all()
    return render_template("contracts/view.html", contract=c, actions=actions, logs=logs, linked_requests=linked_requests)


# ============================================================
#  Print & PDF
# ============================================================
@bp.route("/<int:cid>/print")
@login_required
@require_permission("contracts.view")
def print_contract(cid):
    c = db.session.get(Contract, cid)
    if not c: abort(404)
    return render_template("contracts/print.html", contract=c, auto_print=request.args.get("auto") == "1")

@bp.route("/<int:cid>/pdf")
@login_required
@require_permission("contracts.view")
def contract_pdf(cid):
    return redirect(url_for("contracts.print_contract", cid=cid, pdf_hint="1"))


# ============================================================
#  Workflow Actions
# ============================================================
@bp.route("/<int:cid>/action", methods=["POST"])
@login_required
@require_permission("contracts.edit")
def action_contract(cid):
    c = db.session.get(Contract, cid)
    if not c: abort(404)
    action = request.form.get("action", "").strip()
    comment = request.form.get("comment", "").strip()
    if not action:
        flash("لم يتم تحديد إجراء", "danger")
        return redirect(url_for("contracts.view_contract", cid=cid))
    engine = WorkflowEngine("contract")
    ok, err = engine.execute(c, action, user=current_user, comment=comment)
    if ok:
        db.session.commit()
        flash(f"✅ تم تنفيذ '{action}' بنجاح", "success")
    else:
        flash(f"❌ {err}", "danger")
    return redirect(url_for("contracts.view_contract", cid=cid))


@bp.route("/<int:cid>/delete", methods=["POST"])
@login_required
@require_permission("contracts.delete")
def delete_contract(cid):
    c = db.session.get(Contract, cid)
    if not c: abort(404)
    if c.status == "active" and not current_user.is_admin:
        flash("لا يمكن حذف عقد نشط — يجب إلغاؤه أولاً", "warning")
        return redirect(url_for("contracts.view_contract", cid=cid))
    EquipmentRequest.query.filter_by(matched_contract_id=c.id).update({"matched_contract_id": None})
    number = c.contract_number
    db.session.delete(c)
    db.session.commit()
    flash(f"🗑️ تم حذف العقد {number}", "warning")
    return redirect(url_for("contracts.list_contracts"))


# ============================================================
#  Contract Comparison Helpers
# ============================================================
def _period_dates(period_type, from_str="", to_str=""):
    today = datetime.utcnow().date()
    if period_type == "this_month": return today.replace(day=1), today
    elif period_type == "last_month":
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        try: fair_end = last_month_end.replace(day=today.day)
        except ValueError: fair_end = last_month_end
        return last_month_end.replace(day=1), fair_end
    elif period_type == "last_30": return today - timedelta(days=30), today
    elif period_type == "last_7": return today - timedelta(days=7), today
    elif period_type == "this_year": return today.replace(month=1, day=1), today
    elif period_type == "last_year": return today.replace(year=today.year-1, month=1, day=1), today.replace(year=today.year-1, month=12, day=31)
    elif period_type == "custom" and from_str and to_str:
        try: return (datetime.strptime(from_str, "%Y-%m-%d").date(), datetime.strptime(to_str, "%Y-%m-%d").date())
        except ValueError: return today.replace(day=1), today
    return today.replace(day=1), today


def _aggregate_missions(contract_id, from_date, to_date):
    from collections import defaultdict
    missions = Mission.query.filter(Mission.contract_id == contract_id, func.date(Mission.mission_date) >= from_date.isoformat(), func.date(Mission.mission_date) <= to_date.isoformat()).all()
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
    by_driver = defaultdict(lambda: {"count": 0, "revenue": 0})
    for m in missions:
        if m.driver_name:
            key = m.driver_name.split("(")[0].strip()
            by_driver[key]["count"] += 1
            by_driver[key]["revenue"] += (m.revenue or 0)
    return {"missions": missions, "count": len(missions), "revenue": total_revenue, "cost": total_cost, "profit": profit, "margin": round(margin, 1), "avg_per_mission": round(total_revenue / len(missions), 2) if missions else 0, "by_equipment": dict(by_equipment), "completed": sum(1 for m in missions if m.status in ("completed", "verified", "paid")), "in_progress": sum(1 for m in missions if m.status == "in_progress"), "drivers": sorted([{"name": k, "count": v["count"], "revenue": v["revenue"]} for k, v in by_driver.items()], key=lambda x: x["count"], reverse=True)[:5]}


def _calc_diff(current, previous):
    diff = current - previous
    pct = (diff / abs(previous)) * 100 if previous != 0 else (100 if current > 0 else 0)
    return {"diff": round(diff, 2), "pct": round(pct, 1), "direction": "up" if diff > 0.01 else ("down" if diff < -0.01 else "flat"), "color": "success" if diff >= 0 else "danger"}


# ============================================================
#  Compare Single Contract
# ============================================================
@bp.route("/<int:cid>/compare")
@login_required
@require_permission("contracts.view")
def compare_contract(cid):
    c = db.session.get(Contract, cid)
    if not c: abort(404)
    p1_type = request.args.get("p1", "this_month")
    p1_from, p1_to = _period_dates(p1_type, request.args.get("p1_from", ""), request.args.get("p1_to", ""))
    p2_type = request.args.get("p2", "last_month")
    p2_from, p2_to = _period_dates(p2_type, request.args.get("p2_from", ""), request.args.get("p2_to", ""))
    p1 = _aggregate_missions(cid, p1_from, p1_to)
    p2 = _aggregate_missions(cid, p2_from, p2_to)
    diffs = {"missions": _calc_diff(p1["count"], p2["count"]), "revenue": _calc_diff(p1["revenue"], p2["revenue"]), "cost": _calc_diff(p1["cost"], p2["cost"]), "profit": _calc_diff(p1["profit"], p2["profit"]), "margin": _calc_diff(p1["margin"], p2["margin"]), "avg_per_mission": _calc_diff(p1["avg_per_mission"], p2["avg_per_mission"]), "completed": _calc_diff(p1["completed"], p2["completed"])}
    all_eq = set(p1["by_equipment"].keys()) | set(p2["by_equipment"].keys())
    eq_comp = []
    for eq in sorted(all_eq):
        e1, e2 = p1["by_equipment"].get(eq, {"count": 0, "revenue": 0, "cost": 0}), p2["by_equipment"].get(eq, {"count": 0, "revenue": 0, "cost": 0})
        eq_comp.append({"name": eq, "count1": e1["count"], "count2": e2["count"], "count_diff": e1["count"] - e2["count"], "revenue1": e1["revenue"], "revenue2": e2["revenue"], "revenue_diff": e1["revenue"] - e2["revenue"]})
    eq_comp.sort(key=lambda x: abs(x["count_diff"]), reverse=True)
    insights = []
    if diffs["missions"]["direction"] == "up": insights.append({"type": "success", "icon": "graph-up-arrow", "text": f"المهام زادت بنسبة {abs(diffs['missions']['pct'])}% عن الفترة السابقة"})
    elif diffs["missions"]["direction"] == "down": insights.append({"type": "warning", "icon": "graph-down-arrow", "text": f"⚠️ المهام انخفضت بنسبة {abs(diffs['missions']['pct'])}% — راجع الأداء"})
    if p1["count"] > 0: insights.append({"type": "info", "icon": "bar-chart", "text": f"متوسط الإيراد لكل مهمة: {p1['avg_per_mission']:,.0f} AED"})
    return render_template("contracts/compare.html", contract=c, p1=p1, p2=p2, p1_from=p1_from.strftime("%Y-%m-%d"), p1_to=p1_to.strftime("%Y-%m-%d"), p2_from=p2_from.strftime("%Y-%m-%d"), p2_to=p2_to.strftime("%Y-%m-%d"), p1_type=p1_type, p2_type=p2_type, diffs=diffs, equipment_comparison=eq_comp, insights=insights)


# ============================================================
#  Compare All Contracts (Smart)
# ============================================================
@bp.route("/compare-all")
@login_required
@require_permission("contracts.view")
def compare_all_contracts():
    from datetime import timedelta

    p1_type = request.args.get("p1", "this_month")
    p2_type = request.args.get("p2", "last_month")
    p1_from, p1_to = _period_dates(p1_type)
    p2_from, p2_to = _period_dates(p2_type)
    
    p1_days = (p1_to - p1_from).days + 1
    p2_days = (p2_to - p2_from).days + 1
    
    next_month_start = p1_to + timedelta(days=1)
    next_month_end = next_month_start + timedelta(days=30)
    
    contracts = Contract.query.all()
    
    p1_missions = Mission.query.filter(func.date(Mission.mission_date) >= p1_from.isoformat(), func.date(Mission.mission_date) <= p1_to.isoformat()).all()
    p2_missions = Mission.query.filter(func.date(Mission.mission_date) >= p2_from.isoformat(), func.date(Mission.mission_date) <= p2_to.isoformat()).all()

    projects = {}
    for c in contracts:
        p_name = c.project_name or f"{c.client_entity or ''} - {c.region or ''}".strip("- ")
        if not p_name: p_name = "مشاريع عامة"
        
        if p_name not in projects:
            projects[p_name] = {"name": p_name, "contracts_list": [], "is_new": True, "p1_contracts_count": 0}
        projects[p_name]["contracts_list"].append(c)

    results = []
    insights = []
    totals = {"p1_rev": 0, "p1_cost": 0, "p2_rev": 0, "p2_cost": 0}

    for p_name, p_data in projects.items():
        p1_contracts, p2_contracts, next_contracts = [], [], []
        p1_contracts_at_end, p2_contracts_at_end = [], []
        p1_base_rate, p2_base_rate, next_base_rate = 0, 0, 0
        p1_contract_details = []
        
        for c in p_data["contracts_list"]:
            c_start = c.start_date or c.created_at.date()
            c_end = c.end_date or (datetime.utcnow().date() + timedelta(days=365))
            
            is_active_p1 = (c_start <= p1_to) and (c_end >= p1_from)
            is_active_p2 = (c_start <= p2_to) and (c_end >= p2_from)
            is_active_next = (c_start <= next_month_end) and (c_end >= next_month_start)
            
            is_active_at_end_p1 = (c_start <= p1_to) and (c_end >= p1_to)
            is_active_at_end_p2 = (c_start <= p2_to) and (c_end >= p2_to)

            if is_active_p1: 
                p1_contracts.append(c)
                p_data["p1_contracts_count"] += 1
            if is_active_p2: p2_contracts.append(c)
            if is_active_next: next_contracts.append(c)
            
            if is_active_at_end_p1: p1_contracts_at_end.append(c)
            if is_active_at_end_p2: p2_contracts_at_end.append(c)

            monthly_rate = 0
            for item in c.equipment_items:
                if item.pricing_period == 'monthly':
                    monthly_rate += (item.quantity or 1) * (item.unit_price or 0)
                elif item.pricing_period == 'annual':
                    monthly_rate += ((item.quantity or 1) * (item.unit_price or 0)) / 12

            if is_active_at_end_p1: 
                p1_base_rate += monthly_rate
                if monthly_rate > 0:
                    p1_contract_details.append(f"{c.contract_number} ({monthly_rate:,.0f})")
            if is_active_at_end_p2: 
                p2_base_rate += monthly_rate
            if is_active_next: 
                next_base_rate += monthly_rate

        if not p1_contracts and not p2_contracts and not next_contracts:
            continue
            
        if p2_contracts: p_data["is_new"] = False
            
        all_eq = set()
        for c in p_data["contracts_list"]:
            for item in c.equipment_items:
                all_eq.add(item.equipment_name_ar())
                
        eq_list = []
        has_data = False
        
        for eq_name in all_eq:
            eq_p1_monthly_fixed = 0
            eq_p2_monthly_fixed = 0
            
            p1_fixed, p1_qty, p1_unit_fixed = 0, 0, 0
            for c in p1_contracts:
                for item in c.equipment_items:
                    if item.equipment_name_ar() == eq_name and item.pricing_period != 'per_mission':
                        m_rate = (item.quantity or 1) * (item.unit_price or 0)
                        if item.pricing_period == 'annual': m_rate /= 12
                        
                        p1_qty += (item.quantity or 1)
                        p1_unit_fixed = item.unit_price
                        
                        c_start = c.start_date or c.created_at.date()
                        c_end = c.end_date or (datetime.utcnow().date() + timedelta(days=365))
                        
                        if c_start <= p1_from and c_end >= p1_to:
                            p1_fixed += m_rate 
                        else:
                            active_days = (min(c_end, p1_to) - max(c_start, p1_from)).days + 1
                            p1_fixed += (m_rate / p1_days) * active_days

            p2_fixed, p2_qty, p2_unit_fixed = 0, 0, 0
            for c in p2_contracts:
                for item in c.equipment_items:
                    if item.equipment_name_ar() == eq_name and item.pricing_period != 'per_mission':
                        m_rate = (item.quantity or 1) * (item.unit_price or 0)
                        if item.pricing_period == 'annual': m_rate /= 12
                        
                        p2_qty += (item.quantity or 1)
                        p2_unit_fixed = item.unit_price
                        
                        c_start = c.start_date or c.created_at.date()
                        c_end = c.end_date or (datetime.utcnow().date() + timedelta(days=365))
                        
                        if c_start <= p2_from and c_end >= p2_to:
                            p2_fixed += m_rate
                        else:
                            active_days = (min(c_end, p2_to) - max(c_start, p2_from)).days + 1
                            p2_fixed += (m_rate / p2_days) * active_days
                            
            for c in p1_contracts_at_end:
                for item in c.equipment_items:
                    if item.equipment_name_ar() == eq_name and item.pricing_period != 'per_mission':
                        m_rate = (item.quantity or 1) * (item.unit_price or 0)
                        if item.pricing_period == 'annual': m_rate /= 12
                        eq_p1_monthly_fixed += m_rate

            for c in p2_contracts_at_end:
                for item in c.equipment_items:
                    if item.equipment_name_ar() == eq_name and item.pricing_period != 'per_mission':
                        m_rate = (item.quantity or 1) * (item.unit_price or 0)
                        if item.pricing_period == 'annual': m_rate /= 12
                        eq_p2_monthly_fixed += m_rate

            p1_m = sum(1 for m in p1_missions if m.contract_id in [c.id for c in p1_contracts] and m.equipment_name_ar() == eq_name)
            p1_var = sum((m.cost or 0) for m in p1_missions if m.contract_id in [c.id for c in p1_contracts] and m.equipment_name_ar() == eq_name)
            p1_rev = sum((m.revenue or 0) for m in p1_missions if m.contract_id in [c.id for c in p1_contracts] and m.equipment_name_ar() == eq_name)
            
            p2_m = sum(1 for m in p2_missions if m.contract_id in [c.id for c in p2_contracts] and m.equipment_name_ar() == eq_name)
            p2_var = sum((m.cost or 0) for m in p2_missions if m.contract_id in [c.id for c in p2_contracts] and m.equipment_name_ar() == eq_name)
            p2_rev = sum((m.revenue or 0) for m in p2_missions if m.contract_id in [c.id for c in p2_contracts] and m.equipment_name_ar() == eq_name)

            # ⭐ حساب سعر الوحدة للمهام (للمعدات التي تسعر لكل مهمة)
            p1_unit_var = (p1_var / p1_m) if p1_m > 0 else 0
            p2_unit_var = (p2_var / p2_m) if p2_m > 0 else 0

            p1_total_eq_cost = p1_fixed + p1_var
            p2_total_eq_cost = p2_fixed + p2_var
            
            if p1_m > 0 or p2_m > 0 or p1_fixed > 0 or p2_fixed > 0:
                has_data = True
                eq_list.append({
                    "name": eq_name, "p1_m": p1_m, "p2_m": p2_m, "m_diff": p1_m - p2_m,
                    "p1_cost": p1_total_eq_cost, "p2_cost": p2_total_eq_cost, "cost_diff": p1_total_eq_cost - p2_total_eq_cost,
                    "p1_rev": p1_rev, "p2_rev": p2_rev,
                    "p1_qty": p1_qty, "p2_qty": p2_qty,
                    "p1_unit_fixed": p1_unit_fixed, "p2_unit_fixed": p2_unit_fixed,
                    "p1_unit_var": p1_unit_var, "p2_unit_var": p2_unit_var, # ⭐ أضفنا هذين المتغيرين
                    "eq_p1_monthly": eq_p1_monthly_fixed, "eq_p2_monthly": eq_p2_monthly_fixed,
                    "p1_var": p1_var, "p2_var": p2_var
                })
        
        if not has_data: continue
        
        p1_total_rev = sum(e["p1_rev"] for e in eq_list)
        p1_total_cost = sum(e["p1_cost"] for e in eq_list)
        p2_total_rev = sum(e["p2_rev"] for e in eq_list)
        p2_total_cost = sum(e["p2_cost"] for e in eq_list)
        
        eq_list.sort(key=lambda x: x["p1_cost"] + x["p2_cost"], reverse=True)
        
        results.append({
            "project_name": p_name, "contracts_str": ", ".join(c.contract_number for c in p_data["contracts_list"]),
            "p1_missions": sum(e["p1_m"] for e in eq_list), "p2_missions": sum(e["p2_m"] for e in eq_list),
            "p1_rev": p1_total_rev, "p2_rev": p2_total_rev, "p1_cost": p1_total_cost, "p2_cost": p2_total_cost,
            "savings": p2_total_cost - p1_total_cost, "equipment_details": eq_list, "is_new": p_data["is_new"]
        })
        
        totals["p1_rev"] += p1_total_rev; totals["p1_cost"] += p1_total_cost
        totals["p2_rev"] += p2_total_rev; totals["p2_cost"] += p2_total_cost

        if p_data["is_new"]:
            insights.append({"type": "info", "text": f"<strong>مشروع جديد ({p_name}):</strong> لم يكن هناك عقد سابق. الالتزام الشهري الجديد: <strong>{p1_base_rate:,.0f}</strong> درهم."})
        else:
            rate_diff = p1_base_rate - p2_base_rate
            
            if rate_diff > 100:
                details_str = " + ".join(p1_contract_details) if p1_contract_details else "لا توجد تفاصيل"
                insights.append({
                    "type": "danger", 
                    "text": f"<strong>زيادة في الالتزام الشهري ({p_name}):</strong> الالتزام الشهري الحالي هو <strong>{p1_base_rate:,.0f}</strong> درهم (السابق: {p2_base_rate:,.0f}). <br><span class='fw-bold text-danger'>زيادة دائمة {rate_diff:,.0f} درهم شهرياً.</span><br>↳ <strong>العقود النشطة حالياً:</strong> {details_str}<br><small class='text-muted'>(ملاحظة: الجدول يعرض التكلفة الفعلية المتناسبة مع أيام الشهر، بينما هذا التنبيه يوضح الالتزام الشهري الكامل).</small>"
                })
                
                for eq in eq_list:
                    eq_diff = eq["eq_p1_monthly"] - eq["eq_p2_monthly"]
                    if eq_diff > 100:
                        if eq["p1_qty"] > eq["p2_qty"]:
                            insights.append({"type": "warning", "text": f"↳ ({eq['name']}): الالتزام الجديد يشمل <strong>{eq['p1_qty']}</strong> وحدة نشطة حالياً (مقارنة بـ {eq['p2_qty']} سابقاً)، مما زاد الالتزام الشهري بـ <strong>{eq_diff:,.0f}</strong> درهم."})
                        elif eq["p1_unit_fixed"] > eq["p2_unit_fixed"]:
                            insights.append({"type": "warning", "text": f"↳ ({eq['name']}): ارتفع سعر الوحدة من <strong>{eq['p2_unit_fixed']:,.0f}</strong> إلى <strong>{eq['p1_unit_fixed']:,.0f}</strong>، مما زاد الالتزام الشهري بـ <strong>{eq_diff:,.0f}</strong> درهم."})
                
                if p_data["p1_contracts_count"] > 1:
                    c_names = ", ".join([c.contract_number for c in p1_contracts_at_end])
                    insights.append({"type": "warning", "text": f"↳ السبب الرئيسي: يوجد <strong>{len(p1_contracts_at_end)}</strong> عقود نشطة في نفس الوقت لهذا المشروع ({c_names})، مما يضاعف الالتزام الشهري."})

            elif rate_diff < -100:
                insights.append({"type": "success", "text": f"<strong>وفر حقيقي في سعر العقد ({p_name}):</strong> انخفض الالتزام الشهري من <strong>{p2_base_rate:,.0f}</strong> إلى <strong>{p1_base_rate:,.0f}</strong> درهم. <br><span class='fw-bold text-success'>تم توفير {abs(rate_diff):,.0f} درهم شهرياً.</span>"})

            if next_base_rate > 0 and p2_base_rate > 0:
                forecast_diff = p2_base_rate - next_base_rate
                if forecast_diff > 100:
                    insights.append({"type": "primary", "text": f"🔮 <strong>تنبؤ الشهر القادم ({p_name}):</strong> الالتزام الشهري سيكون <strong>{next_base_rate:,.0f}</strong> درهم. <br><span class='fw-bold text-success'>توفير متوقع: {forecast_diff:,.0f} درهم.</span>"})
                elif forecast_diff < -100:
                    insights.append({"type": "warning", "text": f"🔮 <strong>تنبؤ الشهر القادم ({p_name}):</strong> الالتزام الشهري سيكون <strong>{next_base_rate:,.0f}</strong> درهم. <br><span class='fw-bold text-danger'>زيادة متوقعة: {abs(forecast_diff):,.0f} درهم.</span>"})

    results.sort(key=lambda x: x["savings"], reverse=True)
    
    return render_template("contracts/compare_all.html", results=results, totals=totals, insights=insights, 
                           p1_from=p1_from.strftime("%Y-%m-%d"), p1_to=p1_to.strftime("%Y-%m-%d"), 
                           p2_from=p2_from.strftime("%Y-%m-%d"), p2_to=p2_to.strftime("%Y-%m-%d"), 
                           p1_days=p1_days, p2_days=p2_days,
                           p1_type=p1_type, p2_type=p2_type)