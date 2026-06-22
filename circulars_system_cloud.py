import streamlit as st
import psycopg2

st.title("🔍 تشخيص مشكلة قاعدة البيانات")

# 1. هل Secrets موجود؟
st.subheader("1. فحص Secrets")
if "DB_URL" in st.secrets:
    st.success("✅ DB_URL موجود في Secrets")
    # نخفي الباسوورد
    db_url_masked = st.secrets["DB_URL"].split('@')[0].split(':')[0:2]
    db_url_masked = ':'.join(db_url_masked) + ':****@' + st.secrets["DB_URL"].split('@')[1]
    st.code(db_url_masked)
else:
    st.error("❌ DB_URL مو موجود في Secrets أبداً")
    st.stop()

# 2. جرب الاتصال واطبع الخطأ الحقيقي
st.subheader("2. تجربة الاتصال")
try:
    conn = psycopg2.connect(st.secrets["DB_URL"])
    st.success("✅ الاتصال بقاعدة البيانات شغال 100%")
    conn.close()
except Exception as e:
    st.error(f"❌ خطأ الاتصال الحقيقي:")
    st.code(str(e)) # هذا بيطلع لك سبب الغلط بالضبط
    st.stop()

st.stop()
