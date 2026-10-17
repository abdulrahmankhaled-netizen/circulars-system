"""
سكربت ترقية قاعدة البيانات — يضيف الأعمدة الجديدة بدون فقدان البيانات.
استخدمه عندما تُضاف حقول جديدة إلى موديل موجود.
"""
import os
import sqlite3

# مسار قاعدة البيانات
DB_PATH = os.path.join("instance", "app.db")


def column_exists(cursor, table, column):
    """يتحقق إذا كان العمود موجوداً في الجدول."""
    cursor.execute(f"PRAGMA table_info({table})")
    return column in [row[1] for row in cursor.fetchall()]


def add_column_safe(cursor, table, column, col_type):
    """يضيف عموداً إن لم يكن موجوداً."""
    if not column_exists(cursor, table, column):
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
        cursor.execute(sql)
        print(f"  ✅ أضيف عمود: {table}.{column}")
        return True
    else:
        print(f"  ℹ موجود: {table}.{column}")
        return False


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ قاعدة البيانات غير موجودة: {DB_PATH}")
        print("   شغّل: python init_db.py أولاً")
        return

    print("=" * 60)
    print("  🔧 ترقية قاعدة البيانات")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # ============ الجدول: missions ============
    print("\n📋 الجدول: missions")
    add_column_safe(cursor, "missions", "is_impound", "BOOLEAN DEFAULT 0")
    add_column_safe(cursor, "missions", "qr_code", "TEXT")
    add_column_safe(cursor, "missions", "store_number", "VARCHAR(80)")
    add_column_safe(cursor, "missions", "job_order_id", "VARCHAR(80)")
    add_column_safe(cursor, "missions", "job_id_external", "VARCHAR(80)")
    add_column_safe(cursor, "missions", "payer_type", "VARCHAR(50)")
    add_column_safe(cursor, "missions", "requested_rec_type", "VARCHAR(120)")
    add_column_safe(cursor, "missions", "actual_rec_type", "VARCHAR(120)")
    add_column_safe(cursor, "missions", "job_status", "VARCHAR(50)")
    add_column_safe(cursor, "missions", "sub_status", "VARCHAR(80)")
    add_column_safe(cursor, "missions", "advisor", "VARCHAR(120)")
    add_column_safe(cursor, "missions", "service_centre", "VARCHAR(150)")
    add_column_safe(cursor, "missions", "toll_job_id", "VARCHAR(80)")
    add_column_safe(cursor, "missions", "toll_amount", "FLOAT")
    add_column_safe(cursor, "missions", "created_date", "DATETIME")
    add_column_safe(cursor, "missions", "started_date", "DATETIME")
    add_column_safe(cursor, "missions", "completed_date", "DATETIME")
    # ============ الجدول: invoices ============
    print("\n📋 الجدول: invoices")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number VARCHAR(60) UNIQUE NOT NULL,
            invoice_type VARCHAR(20) NOT NULL DEFAULT 'supplier',
            supplier_id INTEGER,
            contract_id INTEGER,
            mission_id INTEGER,
            customer_name VARCHAR(200),
            customer_phone VARCHAR(40),
            issue_date DATE,
            due_date DATE,
            amount FLOAT DEFAULT 0,
            vat_amount FLOAT DEFAULT 0,
            total_amount FLOAT DEFAULT 0,
            currency VARCHAR(10) DEFAULT 'AED',
            status VARCHAR(20) DEFAULT 'draft',
            pdf_path VARCHAR(255),
            pdf_uploaded_at DATETIME,
            created_by_id INTEGER,
            approved_by_id INTEGER,
            approved_at DATETIME,
            paid_at DATETIME,
            notes TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
            FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE SET NULL,
            FOREIGN KEY (mission_id) REFERENCES missions(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (approved_by_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    print("  ✅ الجدول جاهز")
    # ============ الجدول: contracts ============
    print("\n📋 الجدول: contracts")
    add_column_safe(cursor, "contracts", "client_entity_en", "VARCHAR(150)")
    add_column_safe(cursor, "contracts", "region_en", "VARCHAR(120)")
    # ============ الجدول: equipment_types ============
    print("\n📋 الجدول: equipment_types")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key VARCHAR(80) UNIQUE NOT NULL,
            name_ar VARCHAR(120) NOT NULL,
            name_en VARCHAR(120),
            description TEXT,
            is_active BOOLEAN DEFAULT 1 NOT NULL,
            sort_order INTEGER DEFAULT 100,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("  ✅ الجدول جاهز")
    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("  🎉 اكتملت الترقية بنجاح")
    print("=" * 60)
    print("\n  شغّل الآن: python run.py")


if __name__ == "__main__":
    migrate()