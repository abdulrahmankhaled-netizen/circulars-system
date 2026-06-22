import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, date
import hashlib
from fpdf import FPDF
import io

# --- الإعدادات ---
DB_URL = st.secrets["DB_URL"]
st.set_page_config(page_title="نظام التعاميم", layout="wide")

# --- الاتصال بقاعدة البيانات ---
def get_connection():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT DEFAULT 'user'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS circulars (
                id SERIAL PRIMARY KEY,
                store_id TEXT,
                plate_number TEXT,
                brand_model TEXT,
                emirate TEXT,
                yard TEXT,
                car_status TEXT,
                circular_type TEXT,
                circular_authority TEXT,
                circular_number TEXT,
                circular_status TEXT,
                date_received DATE,
                days_pending INTEGER,
                notes TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"خطأ في قاعدة البيانات: {e}")
    finally:
        cur.close()
        conn.close()

init_db()

# --- تسجيل الدخول ---
def login(username, password):
    conn = get_connection()
    cur = conn.cursor()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    cur.execute("SELECT role FROM users WHERE username=%s AND password=%s", (username, hashed))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else None

# --- واجهة تسجيل الدخول ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'edit_id' not in st.session_state:
    st.session_state.edit_id = None

if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول - نظام التعاميم")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        role = login(username, password)
        if role:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = role
            st.rerun()
        else:
            st.error("بيانات الدخول غلط")
else:
    st.sidebar.success(f"مرحبا {st.session_state.username} | {st.session_state.role}")
    if st.sidebar.button("تسجيل خروج"):
        st.session_state.logged_in = False
        st.session_state.edit_id = None
        st.rerun()

    st.title("🚗 نظام إدارة تعاميم السيارات")
    st.success("النظام شغال على Supabase ☁")

    # --- التبويبات ---
    tab1, tab2, tab3, tab4 = st.tabs(["➕ إضافة تعميم", "📋 عرض التعاميم", "📥 استيراد Excel", "👥 إدارة المستخدمين"])

    # تبويب 1: إضافة + تعديل تعميم
    with tab1:
        # وضع التعديل
        if st.session_state.edit_id:
            st.subheader("✏️ تعديل التعميم")
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM circulars WHERE id=%s", (st.session_state.edit_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()

            with st.form("edit_circular"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    store_id = st.text_input("رقم المتجر", value=row[1] or "")
                    plate_number = st.text_input("رقم اللوحة", value=row[2] or "")
                    brand_model = st.text_input("الماركة والموديل", value=row[3] or "")
                    emirate = st.selectbox("الإمارة", ["دبي", "أبوظبي", "الشارقة", "عجمان", "أم القيوين", "رأس الخيمة", "الفجيرة"], index=["دبي", "أبوظبي", "الشارقة", "عجمان", "أم القيوين", "رأس الخيمة", "الفجيرة"].index(row[4]) if row[4] else 0)
                with col2:
                    yard = st.text_input("الساحة", value=row[5] or "")
                    car_status = st.selectbox("حالة السيارة", ["موجودة", "مباعة", "في الورشة", "محجوزة"], index=["موجودة", "مباعة", "في الورشة", "محجوزة"].index(row[6]) if row[6] else 0)
                    circular_type = st.selectbox("نوع التعميم", ["حجز", "منع بيع", "استعلام", "مخالفة"], index=["حجز", "منع بيع", "استعلام", "مخالفة"].index(row[7]) if row[7] else 0)
                    circular_authority = st.text_input("جهة التعميم", value=row[8] or "")
                with col3:
                    circular_number = st.text_input("رقم التعميم", value=row[9] or "")
                    circular_status = st.selectbox("حالة التعميم", ["مفتوح", "مغلق", "قيد المعالجة"], index=["مفتوح", "مغلق", "قيد المعالجة"].index(row[10]) if row[10] else 0)
                    date_received = st.date_input("تاريخ الاستلام", value=row[11] if row[11] else date.today())
                    notes = st.text_area("ملاحظات", value=row[13] or "")

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.form_submit_button("💾 حفظ التعديلات"):
                        days_pending = (date.today() - date_received).days
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("""
                            UPDATE circulars SET store_id=%s, plate_number=%s, brand_model=%s, emirate=%s, yard=%s,
                            car_status=%s, circular_type=%s, circular_authority=%s, circular_number=%s, circular_status=%s,
                            date_received=%s, days_pending=%s, notes=%s WHERE id=%s
                        """, (store_id, plate_number, brand_model, emirate, yard, car_status, circular_type,
                              circular_authority, circular_number, circular_status, date_received, days_pending,
                              notes, st.session_state.edit_id))
                        conn.commit()
                        cur.close()
                        conn.close()
                        st.session_state.edit_id = None
                        st.success("تم التعديل بنجاح ✅")
                        st.rerun()
                with col_b:
                    if st.form_submit_button("❌ إلغاء"):
                        st.session_state.edit_id = None
                        st.rerun()
        else:
            st.subheader("إضافة تعميم جديد")
            with st.form("add_circular"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    store_id = st.text_input("رقم المتجر")
                    plate_number = st.text_input("رقم اللوحة")
                    brand_model = st.text_input("الماركة والموديل")
                    emirate = st.selectbox("الإمارة", ["دبي", "أبوظبي", "الشارقة", "عجمان", "أم القيوين", "رأس الخيمة", "الفجيرة"])
                with col2:
                    yard = st.text_input("الساحة")
                    car_status = st.selectbox("حالة السيارة", ["موجودة", "مباعة", "في الورشة", "محجوزة"])
                    circular_type = st.selectbox("نوع التعميم", ["حجز", "منع بيع", "استعلام", "مخالفة"])
                    circular_authority = st.text_input("جهة التعميم")
                with col3:
                    circular_number = st.text_input("رقم التعميم")
                    circular_status = st.selectbox("حالة التعميم", ["مفتوح", "مغلق", "قيد المعالجة"])
                    date_received = st.date_input("تاريخ الاستلام", value=date.today())
                    notes = st.text_area("ملاحظات")

                if st.form_submit_button("حفظ التعميم"):
                    days_pending = (date.today() - date_received).days
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO circulars (store_id, plate_number, brand_model, emirate, yard, car_status,
                        circular_type, circular_authority, circular_number, circular_status, date_received,
                        days_pending, notes, created_by)
                        VALUES (%s,%s,%s,%s)
                    """, (store_id, plate_number, brand_model, emirate, yard, car_status, circular_type,
                          circular_authority, circular_number, circular_status, date_received, days_pending,
                          notes, st.session_state.username))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("تم حفظ التعميم بنجاح ✅")
                    st.rerun()

    # تبويب 2: عرض التعاميم + أزرار تعديل وحذف
    with tab2:
        st.subheader("كل التعاميم")
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM circulars ORDER BY created_at DESC", conn)
        conn.close()

        # فلترة
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_emirate = st.selectbox("فلترة بالإمارة", ["الكل"] + list(df['emirate'].dropna().unique()))
        with col2:
            filter_status = st.selectbox("فلترة بالحالة", ["الكل"] + list(df['circular_status'].dropna().unique()))
        with col3:
            search_plate = st.text_input("بحث برقم اللوحة")

        if filter_emirate!= "الكل":
            df = df[df['emirate'] == filter_emirate]
        if filter_status!= "الكل":
            df = df[df['circular_status'] == filter_status]
        if search_plate:
            df = df[df['plate_number'].str.contains(search_plate, na=False)]

        # عرض الجدول مع أزرار
        for index, row in df.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([3,1,1,1])
                with col1:
                    st.write(f"**{row['plate_number']}** | {row['brand_model']} | {row['circular_type']} | {row['circular_status']}")
                with col2:
                    if st.button("✏️ تعديل", key=f"edit_{row['id']}"):
                        st.session_state.edit_id = row['id']
                        st.rerun()
                with col3:
                    if st.button("🗑️ حذف", key=f"delete_{row['id']}"):
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("DELETE FROM circulars WHERE id=%s", (row['id'],))
                        conn.commit()
                        cur.close()
                        conn.close()
                        st.success("تم الحذف ✅")
                        st.rerun()
                with col4:
                    days = row['days_pending']
                    if days > 30:
                        st.error(f"{days} يوم")
                    elif days > 14:
                        st.warning(f"{days} يوم")
                    else:
                        st.info(f"{days} يوم")
                st.divider()

        # تصدير PDF
        if st.button("📄 تصدير PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.add_font('Arial', '', 'arial.ttf', uni=True)
            pdf.set_font('Arial', size=12)
            pdf.cell(200, 10, txt="تقرير التعاميم", ln=True, align='C')
            pdf.ln(10)
            for index, row in df.iterrows():
                pdf.cell(200, 8, txt=f"لوحة: {row['plate_number']} | نوع: {row['circular_type']} | حالة: {row['circular_status']}", ln=True, align='R')
            pdf_output = io.BytesIO()
            pdf.output(pdf_output)
            st.download_button("تحميل PDF", data=pdf_output.getvalue(), file_name="circulars.pdf", mime="application/pdf")

    # تبويب 3: استيراد Excel
    with tab3:
        st.subheader("استيراد من ملف Excel")
        st.info("الأعمدة المطلوبة: store_id, plate_number, brand_model, emirate, yard, car_status, circular_type, circular_authority, circular_number, circular_status, date_received, notes")
        uploaded_file = st.file_uploader("اختار ملف Excel", type=['xlsx', 'xls'])
        if uploaded_file:
            df_excel = pd.read_excel(uploaded_file)
            st.write("معاينة البيانات:")
            st.dataframe(df_excel.head())

            if st.button("استيراد للبيانات"):
                conn = get_connection()
                cur = conn.cursor()
                for index, row in df_excel.iterrows():
                    days_pending = (date.today() - row['date_received'].date()).days if pd.notna(row['date_received']) else 0
                    cur.execute("""
                        INSERT INTO circulars (store_id, plate_number, brand_model, emirate, yard, car_status,
                        circular_type, circular_authority, circular_number, circular_status, date_received,
                        days_pending, notes, created_by)
                        VALUES (%s,%s,%s,%s,%s,%s)
                    """, (row.get('store_id'), row.get('plate_number'), row.get('brand_model'), row.get('emirate'),
                          row.get('yard'), row.get('car_status'), row.get('circular_type'), row.get('circular_authority'),
                          row.get('circular_number'), row.get('circular_status'), row.get('date_received'),
                          days_pending, row.get('notes'), st.session_state.username))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"تم استيراد {len(df_excel)} صف بنجاح ✅")

    # تبويب 4: إدارة المستخدمين - للأدمن فقط
    with tab4:
        if st.session_state.role == 'admin':
            st.subheader("إضافة مستخدم جديد")
            with st.form("add_user"):
                new_username = st.text_input("اسم المستخدم الجديد")
                new_password = st.text_input("كلمة المرور", type="password")
                new_role = st.selectbox("الصلاحية", ["user", "admin"])
                if st.form_submit_button("إضافة"):
                    conn = get_connection()
                    cur = conn.cursor()
                    hashed = hashlib.sha256(new_password.encode()).hexdigest()
                    try:
                        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                                    (new_username, hashed, new_role))
                        conn.commit()
                        st.success("تم إضافة المستخدم ✅")
                    except psycopg2.IntegrityError:
                        st.error("اسم المستخدم موجود مسبقاً")
                    cur.close()
                    conn.close()

            # عرض المستخدمين
            st.subheader("المستخدمين الحاليين")
            conn = get_connection()
            users_df = pd.read_sql_query("SELECT id, username, role FROM users", conn)
            conn.close()
            st.dataframe(users_df, use_container_width=True)
        else:
            st.warning("هذه الصفحة للأدمن فقط")
