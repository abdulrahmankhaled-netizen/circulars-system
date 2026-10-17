"""
دوال مساعدة عامة.
"""
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename


# ============================================================
#  Files
# ============================================================
def allowed_file(filename: str, allowed: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def save_upload(file_storage, subfolder: str, upload_root: Path) -> str:
    """يحفظ ملفاً مرفوعاً ويعيد المسار النسبي."""
    # حماية من القيم النصية
    if not file_storage:
        return None
    if isinstance(file_storage, str):
        return None
    if not hasattr(file_storage, "filename"):
        return None
    if not file_storage.filename:
        return None

    unique = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    safe_name = f"{unique}_{secure_filename(file_storage.filename)}"

    folder = Path(upload_root) / subfolder
    folder.mkdir(parents=True, exist_ok=True)
    file_storage.save(folder / safe_name)

    return f"{subfolder}/{safe_name}".replace("\\", "/")


# ============================================================
#  Supplier Files
# ============================================================
def save_supplier_file(file_storage, supplier_id: int, category: str, upload_root) -> str:
    """
    يحفظ ملفاً خاصاً بمورد.
    category: license | tax | signature | other
    """
    # حماية: يجب أن يكون كائن ملف فعلي
    if not file_storage:
        return None

    if isinstance(file_storage, str):
        return None

    if not hasattr(file_storage, "filename"):
        return None

    if not file_storage.filename:
        return None

    allowed = {"pdf", "png", "jpg", "jpeg"}
    if not allowed_file(file_storage.filename, allowed):
        return None

    unique = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    safe_name = f"{unique}_{secure_filename(file_storage.filename)}"

    folder = Path(upload_root) / "suppliers" / str(supplier_id) / category
    folder.mkdir(parents=True, exist_ok=True)
    file_storage.save(folder / safe_name)

    return f"suppliers/{supplier_id}/{category}/{safe_name}".replace("\\", "/")


# ============================================================
#  Strings
# ============================================================
def slugify_ar(text: str) -> str:
    """ينتج مفتاحاً آمناً من نص عربي أو إنجليزي."""
    if not text:
        return ""
    text = text.strip().lower().replace(" ", "_")
    text = re.sub(r"[^\w\u0600-\u06FF_]+", "", text)
    return text[:80]


def truncate(text: str, length: int = 60, suffix: str = "...") -> str:
    if not text:
        return ""
    return text if len(text) <= length else text[:length] + suffix


# ============================================================
#  Numbers
# ============================================================
def parse_float(value, default=None):
    if value is None or value == "" or value == "N/A":
        return default
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ============================================================
#  Dates
# ============================================================
def parse_date(value, formats=None):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, "date") and not isinstance(value, str):
        try:
            return value.date()
        except Exception:
            pass
    formats = formats or (
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y",
    )
    s = str(value).strip()
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    formats = (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M", "%Y-%m-%d",
        "%d-%b-%Y %I:%M:%S %p", "%d-%b-%Y %H:%M:%S",
    )
    s = str(value).strip()
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ============================================================
#  Generators
# ============================================================
def next_number(prefix: str, current_max: int, year: int = None) -> str:
    """مثال: REQ-2026-0001"""
    year = year or datetime.utcnow().year
    return f"{prefix}-{year}-{current_max + 1:04d}"