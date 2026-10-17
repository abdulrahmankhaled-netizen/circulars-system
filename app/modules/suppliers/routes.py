"""مسارات الموردين."""
from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
)
from flask_login import login_required, current_user

from app.extensions import db
from app.core.permissions import require_permission
from app.core.helpers import save_supplier_file
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.forms import SupplierForm

bp = Blueprint("suppliers", __name__)


# ============================================================
#  List
# ============================================================
@bp.route("/")
@login_required
@require_permission("suppliers.view")
def list_suppliers():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Supplier.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Supplier.company_name_ar.ilike(like),
                Supplier.company_name_en.ilike(like),
                Supplier.trade_license_no.ilike(like),
                Supplier.contact_person.ilike(like),
                Supplier.phone.ilike(like),
            )
        )
    if status_filter:
        query = query.filter(Supplier.status == status_filter)

    suppliers = query.order_by(Supplier.created_at.desc()).all()

    # إحصائيات سريعة
    stats = {
        "total": Supplier.query.count(),
        "active": Supplier.query.filter_by(status="active").count(),
        "expired_licenses": sum(
            1 for s in Supplier.query.all() if s.license_status() == "expired"
        ),
        "pending_signatures": Supplier.query.filter(
            Supplier.signature_file.isnot(None),
            Supplier.signature_approved == False,
        ).count(),
    }

    return render_template(
        "suppliers/list.html",
        suppliers=suppliers,
        q=q,
        status_filter=status_filter,
        stats=stats,
    )


# ============================================================
#  Add
# ============================================================
@bp.route("/add", methods=["GET", "POST"])
@login_required
@require_permission("suppliers.create")
def add_supplier():
    form = SupplierForm()

    if form.validate_on_submit():
        # فحص التكرار
        if Supplier.query.filter_by(
            trade_license_no=form.trade_license_no.data.strip()
        ).first():
            flash("رقم الرخصة مسجل مسبقاً لمورد آخر", "danger")
            return render_template(
                "suppliers/form.html", form=form, title="إضافة مورد", supplier=None
            )

        s = Supplier(
            company_name_ar=form.company_name_ar.data.strip(),
            company_name_en=form.company_name_en.data.strip() if form.company_name_en.data else None,
            trade_license_no=form.trade_license_no.data.strip(),
            trade_license_expiry=form.trade_license_expiry.data,
            transport_permit_no=form.transport_permit_no.data,
            contact_person=form.contact_person.data,
            phone=form.phone.data,
            email=form.email.data,
            address=form.address.data,
            bank_name=form.bank_name.data,
            iban=form.iban.data,
            vat_registered=form.vat_registered.data,
            trn=form.trn.data if form.vat_registered.data else None,
            tax_certificate_expiry=form.tax_certificate_expiry.data if form.vat_registered.data else None,
            authorized_signatory_name=form.authorized_signatory_name.data,
            authorized_signatory_title=form.authorized_signatory_title.data,
            status=form.status.data,
            notes=form.notes.data,
        )
        db.session.add(s)
        db.session.flush()  # للحصول على id قبل حفظ الملفات

        # ============ حفظ الملفات ============
        upload_root = current_app.config["UPLOAD_FOLDER"]

        if form.trade_license_file.data:
            path = save_supplier_file(
                form.trade_license_file.data, s.id, "license", upload_root
            )
            if path:
                s.trade_license_file = path
                s.trade_license_uploaded_at = datetime.utcnow()

        if form.tax_certificate_file.data:
            path = save_supplier_file(
                form.tax_certificate_file.data, s.id, "tax", upload_root
            )
            if path:
                s.tax_certificate_file = path

        if form.signature_file.data:
            path = save_supplier_file(
                form.signature_file.data, s.id, "signature", upload_root
            )
            if path:
                s.signature_file = path
                s.signature_approved = False

        db.session.commit()
        flash(f"✅ تم إضافة المورد '{s.company_name_ar}' بنجاح", "success")
        return redirect(url_for("suppliers.view_supplier", sid=s.id))

    return render_template(
        "suppliers/form.html", form=form, title="إضافة مورد", supplier=None
    )


# ============================================================
#  Edit
# ============================================================
@bp.route("/<int:sid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("suppliers.edit")
def edit_supplier(sid):
    s = db.session.get(Supplier, sid)
    if not s:
        abort(404)

    form = SupplierForm(obj=s)

    if form.validate_on_submit():
        # فحص تكرار رقم الرخصة (مع استثناء هذا المورد)
        existing = Supplier.query.filter_by(
            trade_license_no=form.trade_license_no.data.strip()
        ).first()
        if existing and existing.id != s.id:
            flash("رقم الرخصة مسجل مسبقاً لمورد آخر", "danger")
            return render_template(
                "suppliers/form.html", form=form, title=f"تعديل: {s.display_name}", supplier=s
            )

        s.company_name_ar = form.company_name_ar.data.strip()
        s.company_name_en = form.company_name_en.data.strip() if form.company_name_en.data else None
        s.trade_license_no = form.trade_license_no.data.strip()
        s.trade_license_expiry = form.trade_license_expiry.data
        s.transport_permit_no = form.transport_permit_no.data
        s.contact_person = form.contact_person.data
        s.phone = form.phone.data
        s.email = form.email.data
        s.address = form.address.data
        s.bank_name = form.bank_name.data
        s.iban = form.iban.data
        s.vat_registered = form.vat_registered.data
        s.trn = form.trn.data if form.vat_registered.data else None
        s.tax_certificate_expiry = form.tax_certificate_expiry.data if form.vat_registered.data else None
        s.authorized_signatory_name = form.authorized_signatory_name.data
        s.authorized_signatory_title = form.authorized_signatory_title.data
        s.status = form.status.data
        s.notes = form.notes.data

        # ============ الملفات الجديدة (فقط إذا رُفعت) ============
        upload_root = current_app.config["UPLOAD_FOLDER"]

        if form.trade_license_file.data:
            path = save_supplier_file(
                form.trade_license_file.data, s.id, "license", upload_root
            )
            if path:
                s.trade_license_file = path
                s.trade_license_uploaded_at = datetime.utcnow()

        if form.tax_certificate_file.data:
            path = save_supplier_file(
                form.tax_certificate_file.data, s.id, "tax", upload_root
            )
            if path:
                s.tax_certificate_file = path

        if form.signature_file.data:
            path = save_supplier_file(
                form.signature_file.data, s.id, "signature", upload_root
            )
            if path:
                s.signature_file = path
                # إلغاء الاعتماد لأن التوقيع تغيّر
                s.signature_approved = False
                s.signature_approved_by_id = None
                s.signature_approved_at = None

        db.session.commit()
        flash("✅ تم تحديث بيانات المورد", "success")
        return redirect(url_for("suppliers.view_supplier", sid=s.id))

    return render_template(
        "suppliers/form.html", form=form, title=f"تعديل: {s.display_name}", supplier=s
    )


# ============================================================
#  View
# ============================================================
@bp.route("/<int:sid>")
@login_required
@require_permission("suppliers.view")
def view_supplier(sid):
    s = db.session.get(Supplier, sid)
    if not s:
        abort(404)
    return render_template("suppliers/view.html", supplier=s)


# ============================================================
#  Delete
# ============================================================
# ============================================================
#  Delete
# ============================================================
@bp.route("/<int:sid>/delete", methods=["POST"])
@login_required
@require_permission("suppliers.delete")
def delete_supplier(sid):
    """
    يحذف المورد — مع فحص شامل للارتباطات.
    إذا وُجدت ارتباطات → رسالة واضحة مع روابط.
    """
    s = db.session.get(Supplier, sid)
    if not s:
        abort(404)

    # ============ فحص كل الارتباطات ============
    from app.modules.contracts.models import Contract
    from app.modules.equipment.models import EquipmentPrice

    checks = {
        "contracts": {
            "count": Contract.query.filter_by(supplier_id=sid).count(),
            "label": "عقود",
            "url": url_for("contracts.list_contracts", supplier=sid),
            "icon": "file-earmark-text",
        },
        "equipment_prices": {
            "count": EquipmentPrice.query.filter_by(supplier_id=sid).count(),
            "label": "أسعار معدات",
            "url": url_for("equipment.list_prices", supplier=sid),
            "icon": "tags",
        },
    }

    # جلب الطلبات المرتبطة (غير مباشر — عبر العقود)
    contracts_ids = [c.id for c in Contract.query.filter_by(supplier_id=sid).all()]
    if contracts_ids:
        from app.modules.requests.models import EquipmentRequest
        requests_count = EquipmentRequest.query.filter(
            EquipmentRequest.matched_contract_id.in_(contracts_ids)
        ).count()
        if requests_count > 0:
            checks["requests"] = {
                "count": requests_count,
                "label": "طلبات مرتبطة",
                "url": url_for("requests.list_requests"),
                "icon": "clipboard-plus",
            }

    # ============ احسب الإجمالي ============
    total_blocking = sum(c["count"] for c in checks.values())

    # ============ إذا كان هناك ارتباطات ============
    if total_blocking > 0:
        # جمع كل الأسباب
        reasons = "، ".join(
            f"{c['count']} {c['label']}"
            for c in checks.values() if c["count"] > 0
        )

        flash(
            f"⚠️ لا يمكن حذف المورد '{s.display_name}' — "
            f"مرتبط بـ {reasons}. يجب حذف هذه العناصر أولاً.",
            "warning"
        )
        return redirect(url_for("suppliers.view_supplier", sid=sid))

    # ============ لا يوجد ارتباطات → احذف ============
    name = s.display_name

    try:
        db.session.delete(s)
        db.session.commit()
        flash(f"🗑️ تم حذف المورد '{name}' بنجاح", "success")

    except Exception as e:
        db.session.rollback()
        flash(
            f"❌ فشل حذف المورد '{name}': {str(e)[:100]}...",
            "danger"
        )

    return redirect(url_for("suppliers.list_suppliers"))

# ============================================================
#  Approve / Revoke Signature
# ============================================================
@bp.route("/<int:sid>/approve-signature", methods=["POST"])
@login_required
@require_permission("suppliers.approve")
def approve_signature(sid):
    s = db.session.get(Supplier, sid)
    if not s:
        abort(404)

    if not s.signature_file:
        flash("لا يوجد توقيع مرفوع للاعتماد", "warning")
        return redirect(url_for("suppliers.view_supplier", sid=s.id))

    s.signature_approved = True
    s.signature_approved_by_id = current_user.id
    s.signature_approved_at = datetime.utcnow()
    db.session.commit()
    flash("✅ تم اعتماد التوقيع", "success")
    return redirect(url_for("suppliers.view_supplier", sid=s.id))


@bp.route("/<int:sid>/revoke-signature", methods=["POST"])
@login_required
@require_permission("suppliers.approve")
def revoke_signature(sid):
    s = db.session.get(Supplier, sid)
    if not s:
        abort(404)

    s.signature_approved = False
    s.signature_approved_by_id = None
    s.signature_approved_at = None
    db.session.commit()
    flash("تم إلغاء اعتماد التوقيع", "warning")
    return redirect(url_for("suppliers.view_supplier", sid=s.id))
# ============================================================
#  استخراج بيانات الرخصة (OCR)
# ============================================================
@bp.route("/extract-license", methods=["POST"])
@login_required
@require_permission("suppliers.create")
def extract_license():
    """
    يستقبل ملف الرخصة (PDF/صورة) ويعيد البيانات المستخرجة كـ JSON.
    """
    from flask import jsonify
    from app.core.ocr import extract_license_data

    file = request.files.get("license_file")
    if not file or not file.filename:
        return jsonify({"error": "لم يتم إرسال أي ملف"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff"):
        return jsonify({"error": f"نوع الملف غير مدعوم: {ext}"}), 400

    import tempfile
    import os

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
    try:
        file.save(tmp.name)
        tmp.close()
        result = extract_license_data(tmp.name)
        return jsonify(result)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
