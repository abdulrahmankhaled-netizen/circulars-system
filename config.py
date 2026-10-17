"""
إعدادات التطبيق — تدعم بيئات متعددة.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # ============ General ============
    APP_NAME = os.getenv("APP_NAME", "نظام إدارة العقود")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

    # ============ Database ============
    _db_url = os.getenv("DATABASE_URL", "sqlite:///instance/app.db")
    if _db_url.startswith("sqlite:///") and not _db_url.startswith("sqlite:////"):
        _rel = _db_url.replace("sqlite:///", "")
        if not os.path.isabs(_rel):
            _db_url = f"sqlite:///{(BASE_DIR / _rel).as_posix()}"

    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ============ Uploads ============
    UPLOAD_FOLDER = BASE_DIR / "app" / "static" / "uploads"
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "32")) * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        "pdf", "png", "jpg", "jpeg", "gif",
        "doc", "docx", "xls", "xlsx", "csv",
    }

    # ============ Security ============
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8

    # ============ API ============
    EXTERNAL_API_KEY = os.getenv("EXTERNAL_API_KEY", "dev-api-key")

    # ============ Admin Default ============
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@2026")
    ADMIN_FULL_NAME = os.getenv("ADMIN_FULL_NAME", "مدير النظام")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")

    # ============ Pagination ============
    ITEMS_PER_PAGE = 25