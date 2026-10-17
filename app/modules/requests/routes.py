"""مسارات طلبات المعدات."""
from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, jsonify,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.core.permissions import require_permission, has_permission
from app.core.workflow import WorkflowEngine, available_actions
from app.core.constants import PRIORITIES, EQUIPMENT_TYPES
from app.modules.requests.models import EquipmentRequest, EquipmentRequestItem
from app.modules.requests.forms import EquipmentRequestForm, RequestActionForm

bp = Blueprint("requests", __name__)


# ============================================================
#  Number Generator
# ============================================================
def generate_request_number() -> str:
    """يولّد رقم طلب فريد: REQ-2026-0001"""
    year = datetime.utcnow().year
    # آخر رقم هذه السنة
    last = EquipmentRequest.query.filter(
        EquipmentRequest.request_number.like(f"REQ-{year}-%")
    ).order_by(EquipmentRequest.id.desc()).first()

    if last:
        try:
            n = int(last.request_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f"REQ-{year}-{n:04d}"


# ============================================================
#  List
# ============================================================
@bp.route("/")
@login_required
@require_permission("requests.view")
def list_requests():
    status_filter = request.args.get("status", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    mine = request.args.get("mine", "").strip() == "1"

    query = EquipmentRequest.query

    # إذا كان المستخدم transport_user → يرى طلباته فقط
    if current_user.role_name in ("transport_user",) and not has_permission(
        current_user, "requests.view"
    ):
        query = query.filter(EquipmentRequest.requester_id == current_user.id)
    elif mine:
        query = query.filter(EquipmentRequest.requester_id == current_user.id)

    if status_filter:
        query = query.filter(EquipmentRequest.status == status_filter)
    if priority_filter:
        query = query.filter(EquipmentRequest.priority == priority_filter)

    requests_list = query.order_by(EquipmentRequest.created_at.desc()).all()

    # الإحصائيات
    total = EquipmentRequest.query.count()
    by_status = {}
    for req in EquipmentRequest.query.all():
        by_status[req.status] = by_status.get(req.status, 0) + 1

    stats = {
        "total": total,
        "draft": by_status.get("draft", 0),
        "submitted": by_status.get("submitted", 0),
        "under_review": by_status.get("under_review", 0),
        "approved": by_status.get("approved", 0),
        "contracted": by_status.get("contracted", 0),
        "fulfilled": by_status.get("fulfilled", 0),
        "rejected": by_status.get("rejected", 0),
    }

    return render_template(
        "requests/list.html",
        requests=requests_list,
        status_filter=status_filter,
        priority_filter=priority_filter,
        mine=mine,
        stats=stats,
    )


# ============================================================
#  Add
# ============================================================
@bp.route("/add", methods=["GET", "POST"])
@login_required
@require_permission("requests.create")
def add_request():
    form = EquipmentRequestForm()

    if form.validate_on_submit():
        # فحص البنود — يجب أن يوجد بند واحد صالح على الأقل
        valid_items = [
            item for item in form.items.data
            if item.get("equipment_key") and item.get("quantity", 0) > 0
        ]
        if not valid_items:
            flash("يجب إضافة معدة واحدة على الأقل", "danger")
            return render_template(
                "requests/form.html", form=form, title="طلب معدة جديدة", req=None
            )

        # ============ إنشاء الطلب ============
        req = EquipmentRequest(
            request_number=generate_request_number(),
            requester_id=current_user.id,
            department=form.department.data or current_user.department,
            title=form.title.data.strip(),
            reason=form.reason.data,
            priority=form.priority.data or "normal",
            location=form.location.data,
            region=form.region.data,
            client_entity=form.client_entity.data,
            needed_from=form.needed_from.data,
            needed_until=form.needed_until.data,
            status="draft",
        )
        db.session.add(req)
        db.session.flush()

        # البنود
        for item_data in valid_items:
            item = EquipmentRequestItem(
                request_id=req.id,
                equipment_key=item_data["equipment_key"],
                quantity=item_data["quantity"] or 1,
                notes=item_data.get("notes"),
            )
            db.session.add(item)

        db.session.commit()
        flash(f"✅ تم إنشاء الطلب {req.request_number}", "success")

        # إذا ضغط "حفظ وإرسال"
        if request.form.get("action") == "save_and_submit":
            return redirect(url_for("requests.submit_request", rid=req.id))

        return redirect(url_for("requests.view_request", rid=req.id))

    # تعبئة قيمة افتراضية للبند الأول
    if request.method == "GET" and not form.items.entries:
        form.items.append_entry()

    return render_template(
        "requests/form.html", form=form, title="طلب معدة جديدة", req=None
    )


# ============================================================
#  Edit
# ============================================================
@bp.route("/<int:rid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("requests.edit")
def edit_request(rid):
    req = db.session.get(EquipmentRequest, rid)
    if not req:
        abort(404)

    # لا يمكن التعديل إلا في المسودة
    if req.status != "draft":
        flash("لا يمكن تعديل الطلب بعد تقديمه", "warning")
        return redirect(url_for("requests.view_request", rid=rid))

    # صلاحية المالك أو admin
    if req.requester_id != current_user.id and not current_user.is_admin:
        flash("لا يمكنك تعديل طلب لا تملكه", "danger")
        return redirect(url_for("requests.view_request", rid=rid))

    form = EquipmentRequestForm(obj=req)

    if request.method == "GET":
        # عبّئ البنود
        form.items.entries = []
        for item in req.items:
            form.items.append_entry({
                "equipment_key": item.equipment_key,
                "quantity": item.quantity,
                "notes": item.notes,
            })
        if not form.items.entries:
            form.items.append_entry()

    if form.validate_on_submit():
        valid_items = [
            item for item in form.items.data
            if item.get("equipment_key") and item.get("quantity", 0) > 0
        ]
        if not valid_items:
            flash("يجب إضافة معدة واحدة على الأقل", "danger")
            return render_template(
                "requests/form.html",
                form=form,
                title=f"تعديل الطلب {req.request_number}",
                req=req,
            )

        # تحديث البيانات
        req.title = form.title.data.strip()
        req.department = form.department.data
        req.priority = form.priority.data
        req.location = form.location.data
        req.region = form.region.data
        req.client_entity = form.client_entity.data
        req.needed_from = form.needed_from.data
        req.needed_until = form.needed_until.data
        req.reason = form.reason.data

        # حذف البنود القديمة وإعادة إنشائها
        for old_item in req.items:
            db.session.delete(old_item)
        db.session.flush()

        for item_data in valid_items:
            item = EquipmentRequestItem(
                request_id=req.id,
                equipment_key=item_data["equipment_key"],
                quantity=item_data["quantity"] or 1,
                notes=item_data.get("notes"),
            )
            db.session.add(item)

        db.session.commit()
        flash("✅ تم تحديث الطلب", "success")

        if request.form.get("action") == "save_and_submit":
            return redirect(url_for("requests.submit_request", rid=req.id))

        return redirect(url_for("requests.view_request", rid=req.id))

    return render_template(
        "requests/form.html",
        form=form,
        title=f"تعديل الطلب {req.request_number}",
        req=req,
    )


# ============================================================
#  View
# ============================================================
@bp.route("/<int:rid>")
@login_required
@require_permission("requests.view")
def view_request(rid):
    req = db.session.get(EquipmentRequest, rid)
    if not req:
        abort(404)

    # صلاحية العرض
    if (current_user.role_name == "transport_user"
            and req.requester_id != current_user.id
            and not current_user.is_admin):
        flash("لا تملك صلاحية عرض هذا الطلب", "danger")
        return redirect(url_for("requests.list_requests"))

    # الأزرار المتاحة
    actions = available_actions("equipment_request", req.status, current_user)

    # سجل التغييرات
    from app.modules.workflow.models import WorkflowLog
    logs = WorkflowLog.query.filter_by(
        entity_type="equipment_request", entity_id=req.id
    ).order_by(WorkflowLog.created_at.asc()).all()

    return render_template(
        "requests/view.html",
        req=req,
        actions=actions,
        logs=logs,
    )


# ============================================================
#  Workflow Actions
# ============================================================
def _execute_action(req, action, comment=""):
    """ينفّذ إجراء workflow ويعيد (نجح؟, رسالة)"""
    engine = WorkflowEngine("equipment_request")
    ok, err = engine.execute(
        req, action,
        user=current_user,
        comment=comment,
    )
    if ok:
        # خطافات خاصة
        if action == "start_review":
            req.reviewed_by_id = current_user.id
            req.reviewed_at = datetime.utcnow()
        elif action == "reject":
            req.rejection_reason = comment
            req.reviewed_by_id = current_user.id
            req.reviewed_at = datetime.utcnow()
        elif action == "approve":
            req.reviewed_by_id = current_user.id
            req.reviewed_at = datetime.utcnow()
        elif action == "mark_contracted":
            req.contracted_at = datetime.utcnow()
        db.session.commit()
        return True, ""
    return False, err


@bp.route("/<int:rid>/submit", methods=["POST", "GET"])
@login_required
@require_permission("requests.submit")
def submit_request(rid):
    req = db.session.get(EquipmentRequest, rid)
    if not req:
        abort(404)

    if req.requester_id != current_user.id and not current_user.is_admin:
        flash("فقط مالك الطلب يمكنه تقديمه", "danger")
        return redirect(url_for("requests.view_request", rid=rid))

    ok, err = _execute_action(req, "submit")
    if ok:
        flash(f"📤 تم تقديم الطلب {req.request_number}", "success")
    else:
        flash(f"❌ {err}", "danger")
    return redirect(url_for("requests.view_request", rid=rid))


@bp.route("/<int:rid>/action", methods=["POST"])
@login_required
@require_permission("requests.review")
def action_request(rid):
    """يستقبل أي إجراء من الـ workflow."""
    req = db.session.get(EquipmentRequest, rid)
    if not req:
        abort(404)

    action = request.form.get("action", "").strip()
    comment = request.form.get("comment", "").strip()

    if not action:
        flash("لم يتم تحديد إجراء", "danger")
        return redirect(url_for("requests.view_request", rid=rid))

    ok, err = _execute_action(req, action, comment)
    if ok:
        flash(f"✅ تم تنفيذ '{action}' بنجاح", "success")
    else:
        flash(f"❌ {err}", "danger")
    return redirect(url_for("requests.view_request", rid=rid))


# ============================================================
#  Delete
# ============================================================
@bp.route("/<int:rid>/delete", methods=["POST"])
@login_required
@require_permission("requests.delete")
def delete_request(rid):
    req = db.session.get(EquipmentRequest, rid)
    if not req:
        abort(404)

    if req.status not in ("draft", "rejected", "cancelled") and not current_user.is_admin:
        flash("لا يمكن حذف طلب في هذه الحالة", "warning")
        return redirect(url_for("requests.view_request", rid=rid))

    number = req.request_number
    db.session.delete(req)
    db.session.commit()
    flash(f"🗑️ تم حذف الطلب {number}", "warning")
    return redirect(url_for("requests.list_requests"))


# ============================================================
#  API Helper (لفحص السعر)
# ============================================================
@bp.route("/api/equipment-list")
@login_required
def api_equipment_list():
    """يعيد قائمة المعدات (JSON) — تُستخدم في JS."""
    return jsonify([
        {
            "key": eq["key"],
            "name_ar": eq["name_ar"],
            "name_en": eq.get("name_en", ""),
        }
        for eq in EQUIPMENT_TYPES
    ])