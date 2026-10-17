"""مسارات المعدات والأسعار."""
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort,
)
from flask_login import login_required

from app.extensions import db
from app.core.permissions import require_permission
from app.modules.equipment.models import EquipmentPrice
from app.modules.equipment.forms import EquipmentPriceForm
from app.modules.suppliers.models import Supplier

bp = Blueprint("equipment", __name__)


# ============================================================
#  List
# ============================================================
@bp.route("/")
@login_required
@require_permission("equipment.view")
def list_prices():
    supplier_id = request.args.get("supplier", "").strip()
    equipment_key = request.args.get("equipment", "").strip()
    active_only = request.args.get("active", "1") == "1"

    query = EquipmentPrice.query
    if supplier_id:
        try:
            query = query.filter(EquipmentPrice.supplier_id == int(supplier_id))
        except ValueError:
            pass
    if equipment_key:
        query = query.filter(EquipmentPrice.equipment_key == equipment_key)
    if active_only:
        query = query.filter(EquipmentPrice.is_active == True)

    prices = query.order_by(
        EquipmentPrice.supplier_id,
        EquipmentPrice.equipment_key,
    ).all()

    # الإحصائيات
    stats = {
        "total": EquipmentPrice.query.count(),
        "active": EquipmentPrice.query.filter_by(is_active=True).count(),
        "suppliers": db.session.query(
            EquipmentPrice.supplier_id
        ).distinct().count(),
        "equipment_types": db.session.query(
            EquipmentPrice.equipment_key
        ).distinct().count(),
    }

    # للفلاتر
    suppliers = Supplier.query.filter_by(status="active")\
        .order_by(Supplier.company_name_ar).all()

    from app.core.constants import EQUIPMENT_TYPES

    return render_template(
        "equipment/list.html",
        prices=prices,
        suppliers=suppliers,
        equipment_types=EQUIPMENT_TYPES,
        supplier_filter=supplier_id,
        equipment_filter=equipment_key,
        active_only=active_only,
        stats=stats,
    )


# ============================================================
#  Add
# ============================================================
@bp.route("/add", methods=["GET", "POST"])
@login_required
@require_permission("equipment.create")
def add_price():
    form = EquipmentPriceForm()
    form.supplier_id.choices = [
        (s.id, s.company_name_ar)
        for s in Supplier.query.filter_by(status="active")
                                .order_by(Supplier.company_name_ar).all()
    ]

    # دعم تمرير supplier_id من الرابط
    if request.method == "GET":
        sid = request.args.get("supplier", type=int)
        if sid:
            form.supplier_id.data = sid

    if form.validate_on_submit():
        # فحص التكرار
        existing = EquipmentPrice.query.filter_by(
            supplier_id=form.supplier_id.data,
            equipment_key=form.equipment_key.data,
        ).first()
        if existing:
            flash(
                "هذا السعر موجود مسبقاً لهذا المورد وهذه المعدة — "
                "يمكنك تعديله",
                "warning",
            )
            return redirect(url_for("equipment.edit_price", pid=existing.id))

        p = EquipmentPrice(
            supplier_id=form.supplier_id.data,
            equipment_key=form.equipment_key.data,
            unit_price=form.unit_price.data or 0.0,
            notes=form.notes.data,
            is_active=form.is_active.data,
        )
        db.session.add(p)
        db.session.commit()
        flash("✅ تم إضافة السعر", "success")
        return redirect(url_for("equipment.list_prices"))

    return render_template(
        "equipment/form.html", form=form, title="إضافة سعر معدة", price=None
    )


# ============================================================
#  Edit
# ============================================================
@bp.route("/<int:pid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("equipment.edit")
def edit_price(pid):
    p = db.session.get(EquipmentPrice, pid)
    if not p:
        abort(404)

    form = EquipmentPriceForm(obj=p)
    form.supplier_id.choices = [
        (s.id, s.company_name_ar)
        for s in Supplier.query.order_by(Supplier.company_name_ar).all()
    ]

    if form.validate_on_submit():
        # فحص التكرار (مع استثناء هذا السعر)
        existing = EquipmentPrice.query.filter_by(
            supplier_id=form.supplier_id.data,
            equipment_key=form.equipment_key.data,
        ).first()
        if existing and existing.id != p.id:
            flash("يوجد سعر آخر بنفس المورد والمعدة", "danger")
            return render_template(
                "equipment/form.html",
                form=form,
                title=f"تعديل: {p.equipment_name_ar()}",
                price=p,
            )

        p.supplier_id = form.supplier_id.data
        p.equipment_key = form.equipment_key.data
        p.unit_price = form.unit_price.data or 0.0
        p.notes = form.notes.data
        p.is_active = form.is_active.data

        db.session.commit()
        flash("✅ تم التحديث", "success")
        return redirect(url_for("equipment.list_prices"))

    return render_template(
        "equipment/form.html",
        form=form,
        title=f"تعديل: {p.equipment_name_ar()}",
        price=p,
    )


# ============================================================
#  Delete
# ============================================================
@bp.route("/<int:pid>/delete", methods=["POST"])
@login_required
@require_permission("equipment.delete")
def delete_price(pid):
    p = db.session.get(EquipmentPrice, pid)
    if not p:
        abort(404)

    name = f"{p.equipment_name_ar()} — {p.supplier.company_name_ar}"
    db.session.delete(p)
    db.session.commit()
    flash(f"🗑️ تم حذف السعر ({name})", "warning")
    return redirect(url_for("equipment.list_prices"))


# ============================================================
#  Bulk Add (لإضافة أسعار مورد لعدة معدات بسرعة)
# ============================================================
@bp.route("/supplier/<int:sid>/bulk-add", methods=["GET", "POST"])
@login_required
@require_permission("equipment.create")
def bulk_add_for_supplier(sid):
    supplier = db.session.get(Supplier, sid)
    if not supplier:
        abort(404)

    from app.core.constants import EQUIPMENT_TYPES

    if request.method == "POST":
        created = 0
        updated = 0
        for eq in EQUIPMENT_TYPES:
            key = eq["key"]
            price_str = request.form.get(f"price_{key}", "").strip()
            if not price_str:
                continue
            try:
                price = float(price_str)
            except ValueError:
                continue

            existing = EquipmentPrice.query.filter_by(
                supplier_id=sid, equipment_key=key
            ).first()

            if existing:
                existing.unit_price = price
                existing.is_active = True
                updated += 1
            else:
                p = EquipmentPrice(
                    supplier_id=sid,
                    equipment_key=key,
                    unit_price=price,
                    is_active=True,
                )
                db.session.add(p)
                created += 1

        db.session.commit()
        flash(
            f"✅ تم إضافة {created} سعر وتحديث {updated} سعر "
            f"للمورد {supplier.company_name_ar}",
            "success",
        )
        return redirect(url_for("equipment.list_prices", supplier=sid))

    # نعرض المعدات الحالية والأسعار
    existing = {
        p.equipment_key: p
        for p in EquipmentPrice.query.filter_by(supplier_id=sid).all()
    }

    return render_template(
        "equipment/bulk_add.html",
        supplier=supplier,
        equipment_types=EQUIPMENT_TYPES,
        existing=existing,
    )



# ============================================================
#  Equipment Types (أنواع الآليات)
# ============================================================
def _slugify(text):
    """يحوّل النص إلى مفتاح آمن."""
    import re
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text[:80]


@bp.route("/types")
@login_required
@require_permission("equipment.view")
def list_types():
    """قائمة أنواع المعدات."""
    from app.modules.equipment.models import EquipmentType

    types = EquipmentType.query.order_by(
        EquipmentType.sort_order, EquipmentType.name_ar
    ).all()

    return render_template("equipment/types_list.html", types=types)


@bp.route("/types/add", methods=["GET", "POST"])
@login_required
@require_permission("equipment.create")
def add_type():
    """إضافة نوع معدة."""
    from app.modules.equipment.models import EquipmentType
    from app.modules.equipment.forms import EquipmentTypeForm

    form = EquipmentTypeForm()

    if form.validate_on_submit():
        key = form.key.data.strip() if form.key.data else ""
        if not key:
            key = _slugify(form.name_en.data or form.name_ar.data)

        if not key:
            flash("لا يمكن توليد المفتاح — اكتب اسم إنجليزي", "danger")
            return render_template("equipment/types_form.html", form=form, title="إضافة نوع")

        if EquipmentType.query.filter_by(key=key).first():
            flash(f"المفتاح '{key}' مستخدم مسبقاً", "danger")
            return render_template("equipment/types_form.html", form=form, title="إضافة نوع")

        t = EquipmentType(
            key=key,
            name_ar=form.name_ar.data.strip(),
            name_en=form.name_en.data.strip() if form.name_en.data else None,
            description=form.description.data,
            sort_order=form.sort_order.data or 100,
            is_active=form.is_active.data,
        )
        db.session.add(t)
        db.session.commit()
        flash(f"✅ تم إضافة '{t.name_ar}'", "success")
        return redirect(url_for("equipment.list_types"))

    return render_template("equipment/types_form.html", form=form, title="إضافة نوع معدة")


@bp.route("/types/<int:tid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("equipment.edit")
def edit_type(tid):
    """تعديل نوع معدة."""
    from app.modules.equipment.models import EquipmentType
    from app.modules.equipment.forms import EquipmentTypeForm

    t = db.session.get(EquipmentType, tid)
    if not t:
        abort(404)

    form = EquipmentTypeForm(obj=t)

    if form.validate_on_submit():
        new_key = form.key.data.strip() if form.key.data else t.key

        # فحص التكرار
        existing = EquipmentType.query.filter_by(key=new_key).first()
        if existing and existing.id != t.id:
            flash(f"المفتاح '{new_key}' مستخدم", "danger")
            return render_template("equipment/types_form.html", form=form,
                                    title=f"تعديل: {t.name_ar}", type_obj=t)

        t.key = new_key
        t.name_ar = form.name_ar.data.strip()
        t.name_en = form.name_en.data.strip() if form.name_en.data else None
        t.description = form.description.data
        t.sort_order = form.sort_order.data or 100
        t.is_active = form.is_active.data

        db.session.commit()
        flash("✅ تم التحديث", "success")
        return redirect(url_for("equipment.list_types"))

    return render_template("equipment/types_form.html", form=form,
                            title=f"تعديل: {t.name_ar}", type_obj=t)


@bp.route("/types/<int:tid>/delete", methods=["POST"])
@login_required
@require_permission("equipment.delete")
def delete_type(tid):
    """حذف نوع معدة."""
    from app.modules.equipment.models import EquipmentType, EquipmentPrice
    from app.modules.missions.models import Mission

    t = db.session.get(EquipmentType, tid)
    if not t:
        abort(404)

    # فحص الاستخدام
    prices_count = EquipmentPrice.query.filter_by(equipment_key=t.key).count()
    missions_count = Mission.query.filter_by(equipment_key=t.key).count()

    if prices_count > 0 or missions_count > 0:
        flash(
            f"⚠️ لا يمكن حذف '{t.name_ar}' — مستخدم في "
            f"{prices_count} سعر و {missions_count} مهمة. "
            f"عطّله بدل حذفه.",
            "warning"
        )
        return redirect(url_for("equipment.list_types"))

    name = t.name_ar
    db.session.delete(t)
    db.session.commit()
    flash(f"🗑️ تم حذف '{name}'", "warning")
    return redirect(url_for("equipment.list_types"))
# ============================================================
#  Helper: البحث عن سعر مورد
# ============================================================
@bp.route("/lookup")
@login_required
def lookup_price():
    """
    يعيد السعر (JSON) بناءً على supplier_id و equipment_key.
    يُستخدم في JavaScript لملء السعر تلقائياً.
    """
    from flask import jsonify
    sid = request.args.get("supplier_id", type=int)
    key = request.args.get("equipment_key", "").strip()
    if not sid or not key:
        return jsonify({"found": False, "price": 0})

    p = EquipmentPrice.query.filter_by(
        supplier_id=sid, equipment_key=key, is_active=True
    ).first()

    if p:
        return jsonify({
            "found": True,
            "price": p.unit_price,
            "currency": p.currency,
            "equipment_name_ar": p.equipment_name_ar(),
        })
    return jsonify({"found": False, "price": 0})