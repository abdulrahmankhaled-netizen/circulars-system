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
        # جدول اليوزرات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
        """)

        # جدول التعاميم
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

        # مدير افتراضي
        cur.execute("SELECT * FROM users WHERE username='admin'")
        if not cur.fetchone():
            hashed = hashlib.sha256('admin123'.encode()).hexdigest()
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                        ('admin', hashed, 'مدير'))
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
        st.rerun()

    st.title("🚗 نظام إدارة تعاميم السيارات")
    st.success("النظام شغال على Supabase ☁ | الحساب: admin / admin123")

    st.write("كمل باقي التبويبات هنا...")
