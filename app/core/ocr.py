"""
OCR لقراءة الرخصة التجارية الإماراتية + قراءة الجداول
يدعم: PDF نصي، صور (JPG/PNG)، صيغة Dubai DED، صيغة ADBC، صيغ عامة
"""
import re
from pathlib import Path


# ============================================================
#  Arabic-Indic digits → Latin
# ============================================================
ARABIC_DIGITS = str.maketrans({
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
})


def _to_latin_digits(text: str) -> str:
    return text.translate(ARABIC_DIGITS) if text else ""


def _clean(value):
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    value = value.strip(": -.,*|")
    return value or None


def _normalize_spaces(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


# ============================================================
#  Text extraction
# ============================================================
def _extract_text_from_pdf(path: str) -> str:
    """يستخرج النص + الجداول من PDF."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pip install pdfplumber")

    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # النص العام
            try:
                t = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            except Exception:
                t = page.extract_text() or ""
            if t:
                parts.append(t)

            # الجداول
            try:
                tables = page.extract_tables() or []
                for table in tables:
                    for row in table:
                        row_clean = [
                            str(c or "").strip().replace("\n", " ")
                            for c in row
                        ]
                        if any(row_clean):
                            parts.append(" | ".join(row_clean))
            except Exception:
                pass

    return "\n".join(parts)


def _extract_text_from_image(path: str) -> str:
    """يستخرج النص من صورة عبر Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise RuntimeError("pip install pytesseract pillow")

    # إذا كان Tesseract في مسار غير افتراضي — أزل التعليق عن السطر التالي
    # pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    try:
        img = Image.open(path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        try:
            return pytesseract.image_to_string(img, lang="ara+eng")
        except Exception:
            return pytesseract.image_to_string(img, lang="eng")
    except Exception as e:
        raise RuntimeError(f"فشل في قراءة الصورة: {e}")


# ============================================================
#  Date normalization
# ============================================================
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _normalize_date(date_str):
    """يحوّل أي تاريخ إلى ISO (YYYY-MM-DD)."""
    if not date_str:
        return None

    s = _to_latin_digits(str(date_str)).strip()
    s = re.sub(r"\s+", " ", s)

    # 12/05/2026 — DD/MM/YYYY أو YYYY/MM/DD
    m = re.search(
        r"(\d{1,4})\s*[\-/\.]\s*(\d{1,2})\s*[\-/\.]\s*(\d{1,4})", s
    )
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        try:
            if len(a) == 4:
                year, month, day = int(a), int(b), int(c)
            else:
                day, month, year = int(a), int(b), int(c)
                if year < 100:
                    year += 2000
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            pass

    # 12 May 2026
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m:
        try:
            day = int(m.group(1))
            month = MONTHS.get(m.group(2).lower()[:9])
            year = int(m.group(3))
            if month:
                return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, TypeError):
            pass

    # May 12, 2026
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", s)
    if m:
        try:
            month = MONTHS.get(m.group(1).lower()[:9])
            day = int(m.group(2))
            year = int(m.group(3))
            if month:
                return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, TypeError):
            pass

    return None


# ============================================================
#  PATTERNS — للرخص الإماراتية
# ============================================================

# -------- Company Name (English) --------
COMPANY_EN_PATTERNS = [
    # Dubai DED: Company Name    NAJMAT ALFALAH ... L.L.C
    r"Company\s+Name\s+([A-Z][A-Z0-9][A-Z0-9\s&.,'\-]{5,200}?(?:L\.?L\.?C|LLC|Ltd|Limited|FZE|FZCO|FZ-LLC|LLP))",
    r"Business\s+Name\s+([A-Z][A-Z0-9][A-Z0-9\s&.,'\-]{5,200}?(?:L\.?L\.?C|LLC|Ltd|Limited|FZE|FZCO|FZ-LLC|LLP))",
    r"License\s+Name\s*[:\|]?\s*([A-Z][A-Za-z0-9\s&.,'\-]{3,200})",
    r"Legal\s+Name\s*[:\|]?\s*([A-Z][A-Za-z0-9\s&.,'\-]{3,200})",
    # Fallback: سطر ينتهي بـ LLC/Ltd
    r"^\s*([A-Z][A-Z0-9][A-Z0-9\s&.,'\-]{5,200}?(?:L\.?L\.?C|LLC|Ltd|Limited|FZE|FZCO|FZ-LLC|LLP))\s*$",
]

# -------- Company Name (Arabic) --------
COMPANY_AR_PATTERNS = [
    # اسم الشركة    نجمة الفلاح ... ش.ذ.م.م
    r"اسم\s+الشركة\s+([\u0600-\u06FF][\u0600-\u06FF\s\d\-.]{3,200}?(?:ش\.ذ\.م\.م|ذ\.م\.م|م\.م\.ح|ش\.م\.ح|ش\.م\.خ))",
    r"الاسم\s+التجاري\s+([\u0600-\u06FF][\u0600-\u06FF\s\d\-.]{3,200}?(?:ش\.ذ\.م\.م|ذ\.م\.م|م\.م\.ح|ش\.م\.ح|ش\.م\.خ))",
    # Fallback: أي سطر عربي ينتهي بـ ش.ذ.م.م
    r"^\s*([\u0600-\u06FF][\u0600-\u06FF\s\d\-.]{5,200}?(?:ش\.ذ\.م\.م|ذ\.م\.م|م\.م\.ح|ش\.م\.ح|ش\.م\.خ))\s*$",
]

# -------- License Number --------
LICENSE_PATTERNS = [
    r"License\s+No\.?\s*[:\|]?\s*(\d{4,15})",
    r"Main\s+License\s+No\.?\s*[:\|]?\s*(\d{4,15})",
    r"Trade\s+License\s+No\.?\s*[:\|]?\s*(\d{4,15})",
    r"رقم\s+الرخصة\s*[:\|]?\s*(\d{4,15})",
    r"رقم\s+السجل\s+التجاري\s*[:\|]?\s*(\d{4,15})",
    r"(?:License|رخصة)\D{0,20}?(\d{5,15})",
]

# -------- Expiry Date --------
EXPIRY_PATTERNS = [
    r"Expiry\s+Date\s*[:\|]?\s*(\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
    r"تاريخ\s+الانتهاء\s*[:\|]?\s*(\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
    r"(?:Valid\s+(?:Un)?til|Expires?|ينتهي)\s*[:\|]?\s*(\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
    r"Expiry\s+Date\s*[:\|]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
]

# -------- Issue Date --------
ISSUE_PATTERNS = [
    r"Issue\s+Date\s*[:\|]?\s*(\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
    r"تاريخ\s+الإصدار\s*[:\|]?\s*(\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
    r"Reg\.?\s+Date\s*[:\|]?\s*(\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
    r"تاريخ\s+الاصدار\s*[:\|]?\s*(\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
]

# -------- TRN --------
TRN_PATTERNS = [
    r"(?:TRN|Tax\s+Registration\s+Number|VAT\s+Registration\s+Number)\s*[:\|]?\s*(\d{15})",
    r"(?:T\.?R\.?N)\s*[:\|]?\s*(\d{15})",
    r"الرقم\s+الضريبي\s*[:\|]?\s*(\d{15})",
]

# -------- Phone --------
PHONE_PATTERNS = [
    r"Mobile\s+No\.?\s*[:\|]?\s*((?:\+?971[\s\-]?)?\d{1,3}[\s\-]?\d{3,4}[\s\-]?\d{4})",
    r"Phone\s+No\.?\s*[:\|]?\s*((?:\+?971[\s\-]?)?\d{1,3}[\s\-]?\d{3,4}[\s\-]?\d{4})",
    r"Tel\.?\s*[:\|]?\s*((?:\+?971[\s\-]?)?\d[\d\s\-]{6,18})",
    r"(?:هاتف|موبايل|تليفون)\s*[:\|]?\s*((?:\+?971[\s\-]?)?\d[\d\s\-]{6,18})",
    r"(\+971[\s\-]?\d{1,3}[\s\-]?\d{3,4}[\s\-]?\d{4})",
    r"(\b971[\s\-]?\d{1,3}[\s\-]?\d{3,4}[\s\-]?\d{4}\b)",
    r"(\b0?5\d[\s\-]?\d{3}[\s\-]?\d{4}\b)",
    r"(\b0?[2-9][\s\-]?\d{3}[\s\-]?\d{4}\b)",
]

EMAIL_PATTERN = r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})"
POBOX_PATTERN = r"(?:P\.?\s*O\.?\s*Box|ص\.?\s*ب)\s*[:\|]?\s*(\d{3,6})"


# ============================================================
#  Extractors
# ============================================================
def _try_patterns(text, patterns, date_field=False):
    for pattern in patterns:
        try:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                value = _clean(m.group(1))
                if value:
                    if date_field:
                        normalized = _normalize_date(value)
                        if normalized:
                            return normalized
                    else:
                        return value
        except Exception:
            continue
    return None


def _extract_all(pattern, text):
    try:
        found, seen = [], set()
        for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            v = _clean(m.group(1))
            if v and v not in seen:
                found.append(v)
                seen.add(v)
        return found
    except Exception:
        return []


# ============================================================
#  Main parser
# ============================================================
def _parse_license_text(text: str) -> dict:
    if not text:
        return {}

    text = _to_latin_digits(text)
    text = _normalize_spaces(text)

    result = {}

    # ============ Company Name EN ============
    for pattern in COMPANY_EN_PATTERNS:
        try:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                v = _clean(m.group(1))
                if v and len(v) > 5:
                    result["company_name_en"] = v
                    break
            if result.get("company_name_en"):
                break
        except Exception:
            continue

    # ============ Company Name AR ============
    for pattern in COMPANY_AR_PATTERNS:
        try:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                v = _clean(m.group(1))
                if v and len(v) > 5:
                    result["company_name_ar"] = v
                    break
            if result.get("company_name_ar"):
                break
        except Exception:
            continue

    # Fallback AR: أي سطر فيه ش.ذ.م.م
    if not result.get("company_name_ar"):
        for line in text.split("\n"):
            line = line.strip()
            if not line or len(line) < 10:
                continue
            if re.search(r"(ش\.ذ\.م\.م|ذ\.م\.م|م\.م\.ح|ش\.م\.ح|ش\.م\.خ)", line):
                clean_line = re.sub(
                    r"^(?:اسم\s+الشركة|الاسم\s+التجاري)\s*[:\|]?\s*", "", line
                )
                # احذف الجزء الإنجليزي
                clean_line = re.sub(
                    r"[A-Za-z][A-Za-z0-9\s&.,'\-]{3,}", "", clean_line
                )
                clean_line = _clean(clean_line)
                if clean_line and len(clean_line) > 5:
                    result["company_name_ar"] = clean_line
                    break

    # Fallback AR: أي سطر يبدأ بـ شركة / مؤسسة
    if not result.get("company_name_ar"):
        for line in text.split("\n"):
            line = line.strip()
            if re.search(r"^(?:شركة|مؤسسة)", line) and 5 < len(line) < 200:
                result["company_name_ar"] = _clean(line)
                break

    # ============ License Number ============
    for pattern in LICENSE_PATTERNS:
        try:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                v = _clean(m.group(1))
                if v:
                    result["trade_license_no"] = v
                    break
            if result.get("trade_license_no"):
                break
        except Exception:
            continue

    # ============ Expiry Date ============
    for pattern in EXPIRY_PATTERNS:
        try:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                v = _clean(m.group(1))
                if v:
                    normalized = _normalize_date(v)
                    if normalized:
                        result["trade_license_expiry"] = normalized
                        break
            if result.get("trade_license_expiry"):
                break
        except Exception:
            continue

    # Fallback: آخر تاريخ صالح في النص
    if not result.get("trade_license_expiry"):
        all_dates = re.findall(
            r"\b(\d{1,2}\s*[\-/\.]\s*\d{1,2}\s*[\-/\.]\s*\d{4})\b", text
        )
        valid = []
        for d in all_dates:
            norm = _normalize_date(d)
            if norm:
                year = int(norm.split("-")[0])
                if 2020 <= year <= 2050:
                    valid.append(norm)
        if valid:
            result["trade_license_expiry"] = valid[-1]

    # ============ Issue Date ============
    for pattern in ISSUE_PATTERNS:
        try:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                v = _clean(m.group(1))
                if v:
                    normalized = _normalize_date(v)
                    if normalized:
                        result["trade_license_issue"] = normalized
                        break
            if result.get("trade_license_issue"):
                break
        except Exception:
            continue

    # ============ TRN ============
    for pattern in TRN_PATTERNS:
        try:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                v = _clean(m.group(1))
                if v:
                    result["trn"] = v
                    break
            if result.get("trn"):
                break
        except Exception:
            continue

    # ============ Phone ============
    for pattern in PHONE_PATTERNS:
        phones = _extract_all(pattern, text)
        if phones:
            result["phone"] = phones[0]
            break

    # ============ Email ============
    emails = _extract_all(EMAIL_PATTERN, text)
    if emails:
        result["email"] = emails[0]

    # ============ PO Box ============
    po = _extract_all(POBOX_PATTERN, text)
    if po:
        result["pobox"] = po[0]

    return {k: v for k, v in result.items() if v}


# ============================================================
#  PUBLIC API
# ============================================================
def extract_license_data(file_path: str) -> dict:
    """
    الدالة الرئيسية — تستخرج البيانات من ملف الرخصة.

    Returns:
        dict مع الحقول + raw_text + method
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
                "error": "لم يُستخرج نص كافٍ. ارفع صورة أوضح أو PDF نصي.",
                "raw_text": text or "",
            }

        result = _parse_license_text(text)
        result["raw_text"] = text[:8000]
        result["method"] = method
        return result

    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        import traceback
        return {
            "error": f"خطأ: {e}",
            "traceback": traceback.format_exc()[:2000],
        }