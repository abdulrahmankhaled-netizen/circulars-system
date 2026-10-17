"""مسارات الفواتير."""
from datetime import datetime, date
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, current_app,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.core.permissions import require_permission
from app.core.helpers import save_upload
from app.modules.invoices.models import Invoice
from app.modules.invoices.forms import InvoiceForm
from app.modules.suppliers.models import Supplier
from app.modules.contracts.models import Contract
from app.modules.missions.models import Mission

bp = Blueprint("invoices", __name__)

VAT_RATE = 0.05


def generate_invoice_number(invoice_type="supplier") -> str:
    """INV-S-2026-0001 (مورد) أو INV-C-2026-0001 (عميل)."""
    year = datetime.utcnow().year
    prefix = "INV-S" if invoice_type == "supplier" else "INV-C"
    last = Invoice.query.filter(
        Invoice.invoice_number.like(f"{prefix}-{year}-%")
    ).order_by(Invoice.id.desc()).first()
    if last:
        try:
            n = int(last.invoice_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f"{prefix}-{year}-{n:04d}"


# ============================================================
#  List
# ============================================================
@bp.route("/")
@login_required
@require_permission("invoices.view")
def list_invoices():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    type_filter = request.args.get("type", "").strip()

    query = Invoice.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Invoice.invoice_number.ilike(like),
                Invoice.customer_name.ilike(like),
            )
        )
    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    if type_filter:
        query = query.filter(Invoice.invoice_type == type_filter)

    invoices = query.order_by(Invoice.created_at.desc()).all()

    # ⭐ كشف المهام المكررة في الفواتير (بناءً على Job Order)
    from collections import Counter
    mission_ids = [inv.mission_id for inv in invoices if inv.mission_id]
    mission_counts = Counter(mission_ids)
    duplicate_missions = {mid for mid, count in mission_counts.items() if count > 1}
    
    # تجميع الفواتير المكررة للتنبيه
    duplicates_info = []
    if duplicate_missions:
        for mid in duplicate_missions:
            dup_invoices = [inv for inv in invoices if inv.mission_id == mid]
            mission = dup_invoices[0].mission
            # ⭐ استخدام الـ Job Order للعرض بدلاً من رقم المهمة
            job_ref = (mission.job_order_id or mission.job_id_external or mission.mission_number) if mission else f"#{mid}"
            inv_numbers = ", ".join([inv.invoice_number for inv in dup_invoices])
            duplicates_info.append({
                "mission_number": job_ref,
                "invoices": inv_numbers,
                "count": len(dup_invoices)
            })

    from sqlalchemy import func
    supplier_total = db.session.query(
        func.coalesce(func.sum(Invoice.total_amount), 0)
    ).filter(Invoice.invoice_type == "supplier").scalar()
    customer_total = db.session.query(
        func.coalesce(func.sum(Invoice.total_amount), 0)
    ).filter(Invoice.invoice_type == "customer").scalar()

    stats = {
        "total": Invoice.query.count(),
        "draft": Invoice.query.filter_by(status="draft").count(),
        "submitted": Invoice.query.filter_by(status="submitted").count(),
        "approved": Invoice.query.filter_by(status="approved").count(),
        "paid": Invoice.query.filter_by(status="paid").count(),
        "supplier_total": float(supplier_total or 0),
        "customer_total": float(customer_total or 0),
    }

    return render_template(
        "invoices/list.html",
        invoices=invoices,
        q=q,
        status_filter=status_filter,
        type_filter=type_filter,
        stats=stats,
        duplicate_missions=duplicate_missions,
        duplicates_info=duplicates_info,
    )


# ============================================================
#  Add
# ============================================================
@bp.route("/add", methods=["GET", "POST"])
@login_required
@require_permission("invoices.create")
def add_invoice():
    form = InvoiceForm()
    form.supplier_id.choices = [(0, "— بدون مورد —")] + [
        (s.id, s.company_name_ar)
        for s in Supplier.query.order_by(Supplier.company_name_ar).all()
    ]
    form.contract_id.choices = [(0, "— بدون عقد —")] + [
        (c.id, f"{c.contract_number} — {c.supplier.company_name_ar}")
        for c in Contract.query.order_by(Contract.contract_number).all()
    ]
    # ⭐ عرض الـ Job Order في القائمة المنسدلة
    form.mission_id.choices = [(0, "— اختر المهمة —")] + [
        (m.id, f"Job: {m.job_order_id or m.job_id_external or '—'} | {m.equipment_name_ar()}")
        for m in Mission.query.order_by(Mission.mission_number.desc()).limit(500).all()
    ]

    if request.method == "GET":
        itype = request.args.get("type", "supplier")
        form.invoice_type.data = itype
        form.invoice_number.data = generate_invoice_number(itype)

        mid = request.args.get("mission", type=int)
        if mid:
            m = db.session.get(Mission, mid)
            if m:
                form.mission_id.data = m.id
                form.contract_id.data = m.contract_id
                form.supplier_id.data = m.contract.supplier_id if m.contract else 0
                form.amount.data = m.cost or 0.0
                form.customer_name.data = m.customer_name

    if form.validate_on_submit():
        if form.mission_id.data == 0:
            flash("⚠️ يجب اختيار مهمة مرتبطة بالفاتورة", "danger")
            return render_template("invoices/form.html", form=form, title="فاتورة جديدة", invoice=None)

        if Invoice.query.filter_by(
            invoice_number=form.invoice_number.data.strip()
        ).first():
            flash("رقم الفاتورة مستخدم مسبقاً", "danger")
            return render_template("invoices/form.html", form=form,
                                    title="فاتورة جديدة", invoice=None)

        inv = Invoice(
            invoice_number=form.invoice_number.data.strip(),
            invoice_type=form.invoice_type.data,
            supplier_id=form.supplier_id.data if form.supplier_id.data != 0 else None,
            contract_id=form.contract_id.data if form.contract_id.data != 0 else None,
            mission_id=form.mission_id.data if form.mission_id.data != 0 else None,
            customer_name=form.customer_name.data,
            customer_phone=form.customer_phone.data,
            issue_date=form.issue_date.data,
            due_date=form.due_date.data,
            amount=form.amount.data or 0.0,
            vat_amount=form.vat_amount.data or 0.0,
            total_amount=form.total_amount.data or 0.0,
            status=form.status.data,
            notes=form.notes.data,
            created_by_id=current_user.id,
        )

        if not inv.vat_amount or not inv.total_amount:
            inv.calculate_totals(VAT_RATE)
        else:
            if abs((inv.amount + inv.vat_amount) - inv.total_amount) > 0.01:
                inv.calculate_totals(VAT_RATE)

        if form.pdf_file.data:
            path = save_upload(
                form.pdf_file.data,
                f"invoices/{datetime.utcnow().strftime('%Y%m')}",
                current_app.config["UPLOAD_FOLDER"],
            )
            if path:
                inv.pdf_path = path
                inv.pdf_uploaded_at = datetime.utcnow()

        db.session.add(inv)
        db.session.commit()

        if inv.mission_id:
            _sync_mission_status(inv.mission, inv)
            db.session.commit()

        flash(f"✅ تم إنشاء الفاتورة {inv.invoice_number}", "success")
        return redirect(url_for("invoices.view_invoice", iid=inv.id))

    return render_template("invoices/form.html", form=form,
                            title="فاتورة جديدة", invoice=None)


# ============================================================
#  Edit
# ============================================================
@bp.route("/<int:iid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("invoices.edit")
def edit_invoice(iid):
    inv = db.session.get(Invoice, iid)
    if not inv:
        abort(404)

    if inv.status == "paid" and not current_user.is_admin:
        flash("لا يمكن تعديل فاتورة مدفوعة", "warning")
        return redirect(url_for("invoices.view_invoice", iid=iid))

    form = InvoiceForm(obj=inv)
    form.supplier_id.choices = [(0, "— بدون مورد —")] + [
        (s.id, s.company_name_ar)
        for s in Supplier.query.order_by(Supplier.company_name_ar).all()
    ]
    form.contract_id.choices = [(0, "— بدون عقد —")] + [
        (c.id, f"{c.contract_number} — {c.supplier.company_name_ar}")
        for c in Contract.query.order_by(Contract.contract_number).all()
    ]
    # ⭐ عرض الـ Job Order في القائمة المنسدلة
    form.mission_id.choices = [(0, "— اختر المهمة —")] + [
        (m.id, f"Job: {m.job_order_id or m.job_id_external or '—'} | {m.equipment_name_ar()}")
        for m in Mission.query.order_by(Mission.mission_number.desc()).limit(500).all()
    ]

    if request.method == "GET":
        form.supplier_id.data = inv.supplier_id or 0
        form.contract_id.data = inv.contract_id or 0
        form.mission_id.data = inv.mission_id or 0

    if form.validate_on_submit():
        if form.mission_id.data == 0:
            flash("⚠️ يجب اختيار مهمة مرتبطة بالفاتورة", "danger")
            return render_template("invoices/form.html", form=form, title=f"تعديل: {inv.invoice_number}", invoice=inv)

        existing = Invoice.query.filter_by(
            invoice_number=form.invoice_number.data.strip()
        ).first()
        if existing and existing.id != inv.id:
            flash("رقم الفاتورة مستخدم", "danger")
            return render_template("invoices/form.html", form=form,
                                    title=f"تعديل: {inv.invoice_number}", invoice=inv)

        inv.invoice_number = form.invoice_number.data.strip()
        inv.invoice_type = form.invoice_type.data
        inv.supplier_id = form.supplier_id.data if form.supplier_id.data != 0 else None
        inv.contract_id = form.contract_id.data if form.contract_id.data != 0 else None
        inv.mission_id = form.mission_id.data if form.mission_id.data != 0 else None
        inv.customer_name = form.customer_name.data
        inv.customer_phone = form.customer_phone.data
        inv.issue_date = form.issue_date.data
        inv.due_date = form.due_date.data
        inv.amount = form.amount.data or 0.0
        inv.status = form.status.data
        inv.notes = form.notes.data

        if not form.vat_amount.data or not form.total_amount.data:
            inv.calculate_totals(VAT_RATE)
        else:
            inv.vat_amount = form.vat_amount.data
            inv.total_amount = form.total_amount.data

        if form.pdf_file.data:
            path = save_upload(
                form.pdf_file.data,
                f"invoices/{datetime.utcnow().strftime('%Y%m')}",
                current_app.config["UPLOAD_FOLDER"],
            )
            if path:
                inv.pdf_path = path
                inv.pdf_uploaded_at = datetime.utcnow()

        if inv.status == "approved" and not inv.approved_at:
            inv.approved_by_id = current_user.id
            inv.approved_at = datetime.utcnow()
        if inv.status == "paid" and not inv.paid_at:
            inv.paid_at = datetime.utcnow()

        db.session.commit()

        if inv.mission_id:
            _sync_mission_status(inv.mission, inv)
            db.session.commit()

        flash("✅ تم التحديث", "success")
        return redirect(url_for("invoices.view_invoice", iid=inv.id))

    return render_template("invoices/form.html", form=form,
                            title=f"تعديل: {inv.invoice_number}", invoice=inv)


# ============================================================
#  View
# ============================================================
@bp.route("/<int:iid>")
@login_required
@require_permission("invoices.view")
def view_invoice(iid):
    inv = db.session.get(Invoice, iid)
    if not inv:
        abort(404)
    return render_template("invoices/view.html", invoice=inv)


# ============================================================
#  Delete
# ============================================================
@bp.route("/<int:iid>/delete", methods=["POST"])
@login_required
@require_permission("invoices.delete")
def delete_invoice(iid):
    inv = db.session.get(Invoice, iid)
    if not inv:
        abort(404)

    if inv.status == "paid" and not current_user.is_admin:
        flash("لا يمكن حذف فاتورة مدفوعة", "warning")
        return redirect(url_for("invoices.view_invoice", iid=iid))

    number = inv.invoice_number
    db.session.delete(inv)
    db.session.commit()
    flash(f"🗑️ تم حذف الفاتورة {number}", "warning")
    return redirect(url_for("invoices.list_invoices"))


# ============================================================
#  Quick actions
# ============================================================
@bp.route("/<int:iid>/mark-paid", methods=["POST"])
@login_required
@require_permission("invoices.edit")
def mark_paid(iid):
    inv = db.session.get(Invoice, iid)
    if not inv:
        abort(404)
    inv.status = "paid"
    inv.paid_at = datetime.utcnow()
    db.session.commit()
    if inv.mission_id:
        _sync_mission_status(inv.mission, inv)
        db.session.commit()
    flash("✅ تم تحديد الفاتورة كمدفوعة", "success")
    return redirect(url_for("invoices.view_invoice", iid=iid))


# ============================================================
#  Sync Mission Status
# ============================================================
def _sync_mission_status(mission, invoice):
    """يُحدّث حالة الدفع في المهمة بناءً على الفاتورة."""
    if not mission:
        return
    if invoice.invoice_type == "supplier":
        if invoice.status == "paid":
            mission.supplier_payment_status = "paid"
        elif invoice.status == "cancelled":
            mission.supplier_payment_status = "cancelled"
        else:
            mission.supplier_payment_status = "pending"
    elif invoice.invoice_type == "customer":
        if invoice.status == "paid":
            mission.customer_invoice_status = "paid"
        elif invoice.status in ("submitted", "approved"):
            mission.customer_invoice_status = "invoiced"
        elif invoice.status == "cancelled":
            mission.customer_invoice_status = "cancelled"


# ============================================================
#  Scan Invoice (OCR)
# ============================================================
@bp.route("/extract", methods=["POST"])
@login_required
@require_permission("invoices.create")
def extract_invoice():
    """يستقبل فاتورة ويعيد بياناتها المستخرجة."""
    from flask import jsonify
    from app.core.invoice_ocr import extract_invoice_data
    from app.modules.suppliers.models import Supplier

    file = request.files.get("invoice_file")
    if not file or not file.filename:
        return jsonify({"error": "لم يتم إرسال ملف"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff"):
        return jsonify({"error": f"نوع الملف غير مدعوم: {ext}"}), 400

    import tempfile, os

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
    try:
        file.save(tmp.name)
        tmp.close()

        suppliers = Supplier.query.filter_by(status="active").all()
        result = extract_invoice_data(tmp.name, suppliers)
        return jsonify(result)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ============================================================
#  Grouped View (By Month + Supplier)
# ============================================================
@bp.route("/grouped")
@login_required
@require_permission("invoices.view")
def grouped_invoices():
    """عرض الفواتير مجمّعة حسب الشهر ثم المورد."""
    invoices = Invoice.query.filter(
        Invoice.issue_date.isnot(None)
    ).order_by(
        Invoice.issue_date.desc(),
        Invoice.supplier_id,
    ).all()

    from collections import defaultdict

    grouped = defaultdict(lambda: defaultdict(list))
    month_totals = defaultdict(lambda: {"count": 0, "total": 0})

    for inv in invoices:
        month_key = inv.issue_date.strftime("%Y-%m")
        sup_key = inv.supplier_id or 0
        grouped[month_key][sup_key].append(inv)

        month_totals[month_key]["count"] += 1
        month_totals[month_key]["total"] += inv.total_amount or 0

    grouped_list = []
    for month_key in sorted(grouped.keys(), reverse=True):
        suppliers_in_month = []
        for sup_id, invs in grouped[month_key].items():
            supplier = invs[0].supplier if invs[0].supplier else None
            suppliers_in_month.append({
                "supplier": supplier,
                "invoices": invs,
                "total": sum(i.total_amount or 0 for i in invs),
                "count": len(invs),
            })
        suppliers_in_month.sort(key=lambda x: x["total"], reverse=True)
        grouped_list.append({
            "month": month_key,
            "month_label": invoices[0].issue_date.strftime("%B %Y") if invoices else month_key,
            "suppliers": suppliers_in_month,
            "total": month_totals[month_key]["total"],
            "count": month_totals[month_key]["count"],
        })

    no_date = Invoice.query.filter(Invoice.issue_date.is_(None)).all()

    return render_template(
        "invoices/grouped.html",
        grouped=grouped_list,
        no_date=no_date,
    )