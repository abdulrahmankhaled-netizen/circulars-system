"""
App Factory — ينشئ ويهيّئ التطبيق.
"""
from flask import Flask, render_template, session, request, redirect, url_for, g
from flask_login import current_user

from config import Config
from app.extensions import db, login_manager, csrf, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # تهيئة الإضافات
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # إعدادات Login
    login_manager.login_view = "auth.login"
    login_manager.login_message = "الرجاء تسجيل الدخول للمتابعة"
    login_manager.login_message_category = "warning"

    # تحميل المستخدم
    from app.modules.users.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # تسجيل الـ Blueprints
    _register_blueprints(app)

    # تسجيل Jinja filters و globals
    _register_jinja(app)

    # تسجيل Error Handlers
    _register_errors(app)

    # Context Processor
    @app.context_processor
    def inject_globals():
        return {
            "APP_NAME": app.config["APP_NAME"],
            "current_year": 2026,
        }

    # ⭐ نظام الترجمة (عربي/إنجليزي)
    TRANSLATIONS = {
        'ar': {
            'app_name': 'نظام إدارة العقود', 'home': 'الرئيسية', 'suppliers': 'الموردون',
            'contracts': 'العقود', 'equipment': 'المعدات', 'requests': 'الطلبات',
            'missions': 'المهام', 'invoices': 'الفواتير', 'followup': 'متابعة الدفع',
            'reports': 'التقارير', 'users': 'المستخدمون', 'notifications': 'التنبيهات',
            'logout': 'تسجيل الخروج', 'change_pwd': 'تغيير كلمة المرور', 'profile': 'الحساب',
            'add': 'إضافة', 'new': 'جديد', 'edit': 'تعديل', 'delete': 'حذف',
            'save': 'حفظ', 'cancel': 'إلغاء', 'search': 'بحث', 'filter': 'تصفية',
            'print': 'طباعة', 'export': 'تصدير', 'actions': 'إجراءات', 'back': 'رجوع',
            'view': 'عرض', 'details': 'تفاصيل', 'total': 'الإجمالي', 'amount': 'المبلغ',
            'status': 'الحالة', 'date': 'التاريخ', 'number': 'الرقم', 'name': 'الاسم',
            'active': 'نشط', 'draft': 'مسودة', 'pending': 'معلّق', 'paid': 'مدفوع',
            'contract_no': 'رقم العقد', 'supplier_name': 'المورد', 'region': 'المنطقة',
            'entity': 'الجهة', 'value': 'القيمة', 'equipment_count': 'الآليات', 'missions_count': 'المهام',
        },
        'en': {
            'app_name': 'Contract Management', 'home': 'Dashboard', 'suppliers': 'Suppliers',
            'contracts': 'Contracts', 'equipment': 'Equipment', 'requests': 'Requests',
            'missions': 'Missions', 'invoices': 'Invoices', 'followup': 'Payment Follow-up',
            'reports': 'Reports', 'users': 'Users', 'notifications': 'Notifications',
            'logout': 'Logout', 'change_pwd': 'Change Password', 'profile': 'Profile',
            'add': 'Add', 'new': 'New', 'edit': 'Edit', 'delete': 'Delete',
            'save': 'Save', 'cancel': 'Cancel', 'search': 'Search', 'filter': 'Filter',
            'print': 'Print', 'export': 'Export', 'actions': 'Actions', 'back': 'Back',
            'view': 'View', 'details': 'Details', 'total': 'Total', 'amount': 'Amount',
            'status': 'Status', 'date': 'Date', 'number': 'No.', 'name': 'Name',
            'active': 'Active', 'draft': 'Draft', 'pending': 'Pending', 'paid': 'Paid',
            'contract_no': 'Contract No.', 'supplier_name': 'Supplier', 'region': 'Region',
            'entity': 'Entity', 'value': 'Value', 'equipment_count': 'Equipments', 'missions_count': 'Missions',
        }
    }

    @app.before_request
    def set_language():
        if 'lang' not in session:
            session['lang'] = 'ar' # اللغة الافتراضية

    @app.context_processor
    def inject_translations():
        lang = session.get('lang', 'ar')
        return dict(t=TRANSLATIONS.get(lang, TRANSLATIONS['ar']), current_lang=lang)

    @app.route('/set_lang/<lang>')
    def set_lang(lang):
        if lang in ['ar', 'en']:
            session['lang'] = lang
        return redirect(request.referrer or url_for('dashboard.index'))

    return app


def _register_blueprints(app):
    """يسجّل كل الـ Blueprints هنا."""
    from app.modules.auth.routes import bp as auth_bp
    from app.modules.users.routes import bp as users_bp
    from app.modules.dashboard.routes import bp as dashboard_bp
    from app.modules.suppliers.routes import bp as suppliers_bp
    from app.modules.equipment.routes import bp as equipment_bp
    from app.modules.requests.routes import bp as requests_bp
    from app.modules.contracts.routes import bp as contracts_bp
    from app.modules.missions.routes import bp as missions_bp
    from app.modules.invoices.routes import bp as invoices_bp
    from app.modules.reports.routes import bp as reports_bp
    from app.modules.notifications.routes import bp as notifications_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(suppliers_bp, url_prefix="/suppliers")
    app.register_blueprint(equipment_bp, url_prefix="/equipment")
    app.register_blueprint(requests_bp, url_prefix="/requests")
    app.register_blueprint(contracts_bp, url_prefix="/contracts")
    app.register_blueprint(missions_bp, url_prefix="/missions")
    app.register_blueprint(invoices_bp, url_prefix="/invoices")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")


def _register_jinja(app):
    """Jinja filters و globals."""
    from app.core.workflow import get_state_meta

    @app.template_filter("state_badge")
    def state_badge(state_name, workflow_name):
        meta = get_state_meta(workflow_name, state_name)
        return f'<span class="badge bg-{meta["color"]}">{meta["label_ar"]}</span>'

    @app.template_filter("role_color")
    def role_color(role_name):
        colors = {
            "admin": "danger",
            "manager": "primary",
            "transport_manager": "info",
            "transport_user": "success",
            "finance": "warning",
            "auditor": "secondary",
        }
        return colors.get(role_name, "secondary")

    @app.template_global()
    def has_permission(perm, user=None):
        from app.core.permissions import has_permission as _has
        return _has(user or current_user, perm)


def _register_errors(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500
    @app.route("/health")
    def health():
        """Health check for Render."""
        from app.extensions import db
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ok"}, 200
        except Exception as e:
            return {"status": "error", "detail": str(e)}, 503