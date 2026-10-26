"""مسارات المصادقة."""
from datetime import datetime
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.modules.users.models import User
from app.modules.auth.forms import LoginForm, ChangePasswordForm

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()

        if not user or not user.check_password(form.password.data):
            flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            flash("حسابك معطّل — تواصل مع الإدارة", "warning")
            return render_template("auth/login.html", form=form)

        user.last_login_at = datetime.utcnow()
        user.last_login_ip = request.remote_addr
        db.session.commit()

        login_user(user, remember=form.remember.data)
        flash(f"👋 مرحباً {user.full_name}", "success")

        # الحماية من التوجيه الخبيث (Open Redirect)
        next_url = request.args.get("next")
        if not next_url or urlparse(next_url).netloc != "":
            next_url = url_for("dashboard.index")
        
        return redirect(next_url)

    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("تم تسجيل الخروج", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("كلمة المرور الحالية غير صحيحة", "danger")
            return render_template("auth/change_password.html", form=form)

        if form.new_password.data != form.confirm_password.data:
            flash("كلمتا المرور غير متطابقتين", "danger")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash("✅ تم تغيير كلمة المرور", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/change_password.html", form=form)