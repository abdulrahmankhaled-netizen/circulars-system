"""
OCR واستخراج بيانات الرخصة التجارية.
يدعم PDF (نصي) والصور (JPG/PNG).
"""
import re
from pathlib import Path


# ============================================================
#  Regex Patterns
# ============================================================
RE_COMPANY_EN = re.compile(
    r"(?:Company\s+Name|Trade\s+Name|Legal\s+Name|Name\s+of\s+(?:the\s+)?Company)"
    r"\s*[:\-]\s*([A-Za-z0-9\s&.,'\-]+?)(?:\n|Trade\s+License|License\s+No|$)",
    re.IGNORECASE,
)

RE_COMPANY_AR = re.compile(
    r"(?:اسم\s+الشركة|الاسم\s+التجاري|الاسم\s+القانوني)"
    r"\s*[:\-]\s*([^\n]+?)(?:\n|رقم\s+الرخصة|رقم\s+السجل|$)",
)

RE_LICENSE_NO = re.compile(
    r"(?:Trade\s+License\s+No|License\s+No|Registration\s+No|رقم\s+الرخصة|رقم\s+السجل)"
    r"\s*[:\-]?\s*([0-9]{4,15})",
    re.IGNORECASE,
)

RE_EXPIRY = re.compile(
    r"(?:Expiry\s+Date|Expiration\s+Date|Valid\s+(?:Un)?til|تاريخ\s+الانتهاء)"
    r"\s*[:\-]?\s*([0-9]{1,4}[\-/.][0-9]{1,2}[\-/.][0-9]{2,4})",
    re.IGNORECASE,
)

RE_TRN = re.compile(
    r"(?:TRN|Tax\s+Registration\s+Number|الرقم\s+الضريبي)"
    r"\s*[:\-]?\s*([0-9]{15})",
    re.IGNORECASE,
)


# ============================================================
#  Extract text from PDF
# ============================================================
def _extract_text_from_pdf(path: str) -> str:
    """يستخرج النص من PDF."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "مكتبة pdfplumber غير مثبتة. شغّل: pip install pdfplumber"
        )

    text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text.append(page_text)

    return "\n".join(text)


# ============================================================
#  Extract text from image via OCR
# ============================================================
def _extract_text_from_image(path: str) -> str:
    """يستخرج النص من صورة عبر Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            "مكتبات OCR غير مثبتة. شغّل: pip install pytesseract pillow"
        )

    # على Windows — حدد مسار tesseract.exe إذا لم يكن في PATH
    # pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    try:
        img = Image.open(path)
        try:
            text = pytesseract.image_to_string(img, lang="ara+eng")
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(img, lang="eng")
        return text
    except Exception as e:
        raise RuntimeError(f"فشل في قراءة الصورة: {e}")


# ============================================================
#  Parse extracted text
# ============================================================
def _clean(value):
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return value or None


def _parse_license_text(text: str) -> dict:
    """يحلّل النص المستخرج ويستخرج الحقول."""
    if not text:
        return {}

    result = {}

    # ---- Company Name (English) ----
    m = RE_COMPANY_EN.search(text)
    if m:
        result["company_name_en"] = _clean(m.group(1))

    # ---- Company Name (Arabic) ----
    m = RE_COMPANY_AR.search(text)
    if m:
        result["company_name_ar"] = _clean(m.group(1))

    # ---- License Number ----
    m = RE_LICENSE_NO.search(text)
    if m:
        result["trade_license_no"] = m.group(1).strip()

    # ---- Expiry Date ----
    m = RE_EXPIRY.search(text)
    if m:
        date_str = m.group(1).strip()
        result["trade_license_expiry"] = _normalize_date(date_str)

    # ---- TRN ----
    m = RE_TRN.search(text)
    if m:
        result["trn"] = m.group(1).strip()

    # ---- Fallback: look for lines with LLC/L.L.C ----
    if not result.get("company_name_en"):
        for line in text.split("\n"):
            line = line.strip()
            if re.search(r"\b(L\.?L\.?C|Ltd|Limited|LLC|FZE|FZCO|FZ-LLC)\b", line, re.IGNORECASE):
                if 5 < len(line) < 150:
                    result["company_name_en"] = line
                    break

    return result


def _normalize_date(date_str: str):
    """يحوّل التواريخ إلى ISO (YYYY-MM-DD)."""
    if not date_str:
        return None

    date_str = date_str.strip()
    parts = re.split(r"[\-/.]", date_str)

    if len(parts) != 3:
        return None

    try:
        a, b, c = parts
        if len(a) == 4:
            year, month, day = int(a), int(b), int(c)
        else:
            day, month, year = int(a), int(b), int(c)
            if year < 100:
                year += 2000

        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None

        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, IndexError):
        return None


# ============================================================
#  Main API
# ============================================================
def extract_license_data(file_path: str) -> dict:
    """
    الدالة الرئيسية — تستخرج البيانات من ملف الرخصة.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext == ".pdf":
            text = _extract_text_from_pdf(file_path)
            method = "pdf"
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"):
            text = _extract_text_from_image(file_path)
            method = "ocr"
        else:
            return {"error": f"نوع الملف غير مدعوم: {ext}"}

        if not text or len(text.strip()) < 10:
            return {
                "error": "لم يُستخرج نص كافٍ من الملف. قد يكون صورة ممسوحة بجودة منخفضة.",
                "raw_text": text,
            }

        result = _parse_license_text(text)
        result["raw_text"] = text[:3000]
        result["method"] = method
        return result

    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"خطأ غير متوقع: {e}"}