#!/bin/bash
set -e

echo "🚀 بدء تشغيل نظام إدارة العقود..."

# 1) تهيئة قاعدة البيانات (آمن — لا يُعيد إنشاء الموجود)
echo "🔧 تهيئة قاعدة البيانات..."
python init_db.py || echo "ℹ️ DB موجودة مسبقاً"

# 2) ترقية الأعمدة الجديدة (آمن — يفحص قبل الإضافة)
echo "🔧 ترقية المخطط..."
python migrate_db.py || echo "ℹ️ لا حاجة لترقية"

# 3) تشغيل gunicorn
# ملاحظة: --workers 1 --threads 8 بسبب قيود SQLite (شرح أدناه)
echo "🌐 تشغيل Gunicorn على المنفذ ${PORT:-8000}..."
exec gunicorn \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 1 \
    --threads 8 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    run:app