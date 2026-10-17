"""
تهيئة قاعدة البيانات + المستخدم الأول + البيانات الأساسية.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.core.constants import ROLES

# ============ استيراد كل الموديلات لضمان إنشاء جداولها ============
from app.modules.users.models import User, Role
from app.modules.workflow.models import WorkflowLog, NotificationQueue, AuditLog
from app.modules.suppliers.models import Supplier
from app.modules.equipment.models import EquipmentPrice
from app.modules.requests.models import EquipmentRequest, EquipmentRequestItem
from app.modules.contracts.models import Contract, ContractEquipment
from app.modules.missions.models import Mission
from app.modules.invoices.models import Invoice
app = create_app()


def seed_roles():
    """ينشئ الأدوار الأساسية."""
    for role_key, role_data in ROLES.items():
        if not Role.query.filter_by(name=role_key).first():
            r = Role(
                name=role_key,
                label_ar=role_data["label_ar"],
                description=role_data.get("description", ""),
                permissions=",".join(role_data.get("permissions", [])),
                is_system=True,
            )
            db.session.add(r)
    db.session.commit()
    print("✅ الأدوار جاهزة")


def seed_admin():
    """ينشئ المستخدم الأول (admin)."""
    cfg = app.config
    if User.query.filter_by(username=cfg["ADMIN_USERNAME"]).first():
        print(f"ℹ المستخدم '{cfg['ADMIN_USERNAME']}' موجود مسبقاً")
        return

    admin_role = Role.query.filter_by(name="admin").first()
    admin = User(
        username=cfg["ADMIN_USERNAME"],
        full_name=cfg["ADMIN_FULL_NAME"],
        email=cfg["ADMIN_EMAIL"],
        role_id=admin_role.id,
        is_active=True,
        is_verified=True,
    )
    admin.set_password(cfg["ADMIN_PASSWORD"])
    db.session.add(admin)
    db.session.commit()
    print(f"✅ تم إنشاء admin: {cfg['ADMIN_USERNAME']} / {cfg['ADMIN_PASSWORD']}")
def seed_equipment_types():
    """ينسخ أنواع المعدات من constants إلى قاعدة البيانات."""
    from app.modules.equipment.models import EquipmentType
    from app.core.constants import EQUIPMENT_TYPES

    if EquipmentType.query.count() > 0:
        print(f"ℹ يوجد {EquipmentType.query.count()} نوع معدة")
        return

    count = 0
    for i, eq in enumerate(EQUIPMENT_TYPES):
        t = EquipmentType(
            key=eq["key"],
            name_ar=eq["name_ar"],
            name_en=eq.get("name_en", ""),
            sort_order=(i + 1) * 10,
            is_active=True,
        )
        db.session.add(t)
        count += 1
    db.session.commit()
    print(f"✅ تم إضافة {count} نوع معدة")

def main():
    print("=" * 60)
    print(f"  تهيئة قاعدة البيانات — {app.config['APP_NAME']}")
    print("=" * 60)

    with app.app_context():
        os.makedirs("instance", exist_ok=True)
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

        db.create_all()
        print("✅ الجداول جاهزة")

        seed_roles()
        seed_admin()
        seed_equipment_types()

    print("=" * 60)
    print("  🎉 التهيئة اكتملت بنجاح")
    print("  شغّل: python run.py")
    print("  ثم افتح: http://127.0.0.1:5000")
    print("=" * 60)


if __name__ == "__main__":
    main()

