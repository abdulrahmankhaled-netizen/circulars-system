"""مسارات إدارة المستخدمين."""
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.core.permissions import require_permission
from app.modules.users.models import User, Role
from app.modules.users.forms import UserForm

bp = Blueprint("users", __name__)


@bp.route("/")
@login_required
@require_permission("users.view")
def list_users():
    users = User.query.order_by(User.id.desc()).all()
    return render_template("users/list.html", users=users)


@bp.route("/add", methods=["GET", "POST"])
@login_required
@require_permission("users.create")
def add_user():
    form = UserForm()
    form.role_id.choices = [(r.id, r.label_ar) for r in Role.query.all()]

    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash("اسم المستخدم مستخدم مسبقاً", "danger")
            return render_template("users/form.html", form=form, title="إضافة مستخدم")

        if not form.password.data:
            flash("كلمة المرور مطلوبة", "danger")
            return render_template("users/form.html", form=form, title="إضافة مستخدم")

        u = User(
            username=form.username.data.strip(),
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip() if form.email.data else None,
            phone=form.phone.data,
            department=form.department.data,
            role_id=form.role_id.data,
            is_active=form.is_active.data,
            is_verified=True,
        )
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        flash(f"✅ تم إنشاء المستخدم {u.full_name}", "success")
        return redirect(url_for("users.list_users"))

    return render_template("users/form.html", form=form, title="إضافة مستخدم")


@bp.route("/<int:uid>/edit", methods=["GET", "POST"])
@login_required
@require_permission("users.edit")
def edit_user(uid):
    u = db.session.get(User, uid)
    if not u:
        abort(404)

    form = UserForm(obj=u)
    form.role_id.choices = [(r.id, r.label_ar) for r in Role.query.all()]

    if form.validate_on_submit():
        u.username = form.username.data.strip()
        u.full_name = form.full_name.data.strip()
        u.email = form.email.data.strip() if form.email.data else None
        u.phone = form.phone.data
        u.department = form.department.data
        u.role_id = form.role_id.data
        u.is_active = form.is_active.data

        if form.password.data:
            u.set_password(form.password.data)

        db.session.commit()
        flash("✅ تم التحديث", "success")
        return redirect(url_for("users.list_users"))

    return render_template("users/form.html", form=form,
                           title=f"تعديل: {u.full_name}", user=u)


@bp.route("/<int:uid>/toggle", methods=["POST"])
@login_required
@require_permission("users.edit")
def toggle_user(uid):
    u = db.session.get(User, uid)
    if not u:
        abort(404)

    if u.id == current_user.id:
        flash("لا يمكنك تعطيل نفسك", "warning")
        return redirect(url_for("users.list_users"))

    u.is_active = not u.is_active
    db.session.commit()
    flash("تم تحديث الحالة", "info")
    return redirect(url_for("users.list_users"))