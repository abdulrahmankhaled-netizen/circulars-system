"""
OCR لقراءة فواتير الموردين واستخراج البيانات.
"""
import re
from pathlib import Path
import pytesseract

import os
import shutil

# البحث التلقائي عن Tesseract (يعمل على Windows و Docker)
if os.name == 'nt':  # إذا كنت تستخدم Windows محلياً
    local_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    user_tess = os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe")
    if os.path.exists(local_tess):
        pytesseract.pytesseract.tesseract_cmd = local_tess
    elif os.path.exists(user_tess):
        pytesseract.pytesseract.tesseract_cmd = user_tess
# في بيئة Docker (Linux)، المكتبة ستجده تلقائياً ولن نحتاج لتحديد المسار
def _extract_text_from_pdf(path: str) -> str:
    text = ""
    # 1. المحاولة الأولى: قراءة نصية عادية (pdfplumber)
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                parts.append(t)
        text = "\n".join(parts)
    except Exception:
        pass

    def is_meaningful(t):
        """دالة لفحص ما إذا كان النص المستخرج مفيداً أم مجرد أرقام وشوائب"""
        if not t or len(t.strip()) < 20: return False
        # إذا كان النص يتكون فقط من أرقام وعلامات ترقيم (مثل شبكة الجدول 1 1 1)
        letters = sum(1 for c in t if c.isalpha())
        alnum = sum(1 for c in t if c.isalnum())
        if alnum == 0: return False
        # يجب أن يحتوي النص على 20% على الأقل من الحروف الحقيقية
        return (letters / alnum) > 0.2

    # 2. المحاولة الثانية: إذا فشل النص العادي، نستخدم PyMuPDF (يجلب النص المخفي بدقة)
    if not is_meaningful(text):
        text = ""
        try:
            import pymupdf  # مكتبة fitz الجديدة
            doc = pymupdf.open(path)
            for page in doc:
                text += page.get_text("text") + "\n"
        except Exception:
            pass

    # 3. المحاولة الثالثة: إذا كان الملف صورة ممسوحة، نستخدم OCR
    if not is_meaningful(text):
        text = ""
        try:
            import pymupdf
            from PIL import Image
            import io
            doc = pymupdf.open(path)
            for page in doc:
                # تحويل الصفحة لصورة بدقة عالية جداً لقراءة الجداول
                pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                # تحويل الصورة لرمادي (Grayscale) لتقليل تشويش الخطوط
                img = img.convert('L')
                try:
                    text += pytesseract.image_to_string(img, lang="ara+eng") + "\n"
                except Exception:
                    text += pytesseract.image_to_string(img, lang="eng") + "\n"
        except Exception as e:
            raise RuntimeError(f"فشل قراءة الـ PDF: {e}")

    return text

def _extract_text_from_image(path: str) -> str:
    from PIL import Image
    img = Image.open(path).convert('L') # تحويل لرمادي
    try:
        return pytesseract.image_to_string(img, lang="ara+eng")
    except Exception:
        return pytesseract.image_to_string(img, lang="eng")

def _normalize_date(date_str):
    if not date_str: return None
    s = str(date_str).strip().lower()
    
    # صيغة أرقام: 30-09-2026
    m = re.search(r"(\d{1,4})\s*[\-/\.]\s*(\d{1,2})\s*[\-/\.]\s*(\d{1,4})", s)
    if m:
        try:
            a, b, c = m.group(1), m.group(2), m.group(3)
            if len(a) == 4: return f"{int(a):04d}-{int(b):02d}-{int(c):02d}"
            else:
                y = int(c) + 2000 if int(c) < 100 else int(c)
                return f"{y:04d}-{int(b):02d}-{int(a):02d}"
        except: pass
        
    # صيغة حروف: 30-Sept-2026
    m = re.search(r"(\d{1,2})\s*[\-/\s]\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[\-/\s]\s*(\d{2,4})", s)
    if m:
        try:
            d, mon, y = m.group(1), m.group(2), m.group(3)
            y = int(y) + 2000 if int(y) < 100 else int(y)
            months = {'jan':1, 'feb':2, 'mar':3, 'apr':4, 'may':5, 'jun':6, 'jul':7, 'aug':8, 'sep':9, 'sept':9, 'oct':10, 'nov':11, 'dec':12}
            mo = months.get(mon[:3].lower(), 1)
            return f"{y:04d}-{mo:02d}-{int(d):02d}"
        except: pass
        
    return None

def _clean_text(text: str) -> str:
    if not text: return ""
    # تحويل الأرقام العربية إلى إنجليزية
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    # تنظيف المسافات
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text

def _parse_amount(text, patterns):
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", "").strip())
            except: pass
    return 0.0

def _parse_invoice_text(text):
    if not text: return {}
    
    text = _clean_text(text)
    result = {}

    # 1. رقم الفاتورة
    m = re.search(r"(?:Invoice|INV|فاتورة)[\s\S]{0,10}?(?:#|No\.?|رقم)?[\s:\-]*([A-Za-z0-9\-_/]+)", text, re.IGNORECASE)
    if m:
        inv_num = m.group(1).strip()
        if not inv_num.isalpha() and inv_num.lower() not in ['date', 'tax', 'total']:
            result["invoice_number"] = inv_num

    # 2. التاريخ
    m = re.search(r"(?:Date|تاريخ|ies)[\s\S]{0,15}?(\d{1,2}[\s\-\.]+[A-Za-z]+[\s\-\.]+\d{2,4}|\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})", text, re.IGNORECASE)
    if m:
        result["issue_date"] = _normalize_date(m.group(1))

    # 3. المبالغ
    subtotal = _parse_amount(text, [
        r"(?:Subtotal|Sub-total|Total\s*Before\s*Tax|المجموع\s*قبل)[\s\S]{0,15}?([\d,]+\.\d{2})",
        r"([\d,]+\.\d{2})\s*(?:Subtotal|Sub-total)"
    ])

    vat = _parse_amount(text, [
        r"(?:Sales\s*Tax|VAT|Tax|ضريبة)[\s\S]{0,25}?([\d,]+\.\d{2})",
        r"([\d,]+\.\d{2})\s*(?:VAT|Tax)"
    ])

    total = _parse_amount(text, [
        r"(?<!Sub)(?:Grand\s*Total|Total\s*Amount|Total|الإجمالي)[\s\S]{0,15}?([\d,]+\.\d{2})",
        r"([\d,]+\.\d{2})\s*(?:Grand\s*Total|Total)"
    ])

    # معالجة النواقص
    if total > 0 and subtotal == 0 and vat == 0:
        subtotal = round(total / 1.05, 2)
        vat = round(total - subtotal, 2)
    elif subtotal > 0 and vat == 0 and total == 0:
        vat = round(subtotal * 0.05, 2)
        total = round(subtotal + vat, 2)

    result["amount"] = subtotal
    result["vat_amount"] = vat
    result["total_amount"] = total

    return result

def extract_invoice_data(file_path: str, suppliers=None):
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext == ".pdf":
            text = _extract_text_from_pdf(file_path)
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"):
            text = _extract_text_from_image(file_path)
        else:
            return {"error": f"نوع الملف غير مدعوم: {ext}"}

        if not text or len(text.strip()) < 10:
            return {"error": "لم يُستخرج نص كافٍ من الفاتورة", "raw_text": text}

        # ⭐ طباعة النص في الشاشة السوداء للتشخيص (كما فعلنا سابقاً)
        print("\n" + "="*50)
        print("RAW TEXT EXTRACTED:")
        print(text[:1000]) # نطبع أول 1000 حرف فقط لتجنب إغراق الشاشة
        print("="*50 + "\n")

        data = _parse_invoice_text(text)

        # مطابقة المورد
        if suppliers:
            clean_text_nospace = re.sub(r'\s+', '', text).lower()
            for s in suppliers:
                if s.company_name_en and len(s.company_name_en) > 4:
                    if s.company_name_en.lower() in text.lower():
                        data["supplier_id"] = s.id
                        data["supplier_name"] = s.company_name_ar
                        break
                if s.company_name_ar and len(s.company_name_ar) > 4:
                    if s.company_name_ar in text:
                        data["supplier_id"] = s.id
                        data["supplier_name"] = s.company_name_ar
                        break
                if s.trn:
                    clean_trn = re.sub(r'\s+', '', str(s.trn)).lower()
                    if clean_trn and clean_trn in clean_text_nospace:
                        data["supplier_id"] = s.id
                        data["supplier_name"] = s.company_name_ar
                        break

        data["raw_text"] = text
        return data

    except Exception as e:
        return {"error": f"خطأ: {e}"}