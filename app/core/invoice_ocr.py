"""
OCR لقراءة فواتير الموردين واستخراج البيانات.
يدعم PDF وصور (JPG/PNG) — عربي وإنجليزي.
"""
import re
from pathlib import Path
import pytesseract

# ⭐ إخبار النظام بمكان Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\Abdulrahman.khaled\AppData\Local\Tesseract-OCR\tesseract.exe"

# ============================================================
#  استخراج النص
# ============================================================
def _extract_text_from_pdf(path: str) -> str:
    """
    يستخرج النص من PDF. 
    إذا كان PDF ممسوحاً أو نصه غير مفهوم، يحوله إلى صور ويقرأها بـ OCR.
    """
    text = ""
    
    # المحاولة 1: قراءة نصية عادية
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

    # دالة للتحقق مما إذا كان النص المستخرج مفيداً أم مجرد شوائب (مثل 1 1 1 1)
    def is_meaningful(t):
        if not t or len(t.strip()) < 20: 
            return False
        # حساب نسبة الحروف الأبجدية إلى إجمالي الحروف والأرقام
        letters = sum(1 for c in t if c.isalpha())
        alnum = sum(1 for c in t if c.isalnum())
        if alnum == 0: 
            return False
        # إذا كانت الحروف الحقيقية أقل من 40%، فهذا يعني أنه ليس نصاً حقيقياً
        return (letters / alnum) > 0.4

    # المحاولة 2: إذا كان النص غير مفيد (أو صورة)، نستخدم OCR
    if not is_meaningful(text):
        try:
            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image
            import io

            # ⭐ مسار Tesseract الخاص بك
            pytesseract.pytesseract.tesseract_cmd = r"C:\Users\Abdulrahman.khaled\AppData\Local\Tesseract-OCR\tesseract.exe"

            doc = fitz.open(path)
            text_parts = []
            for page in doc:
                # تحويل الصفحة لصورة بدقة عالية (لتكون واضحة للقراءة)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes()))
                try:
                    # القراءة بالعربية والإنجليزية
                    text_parts.append(pytesseract.image_to_string(img, lang="ara+eng"))
                except Exception:
                    # إذا لم تكن اللغة العربية مثبتة في Tesseract
                    text_parts.append(pytesseract.image_to_string(img, lang="eng"))
            text = "\n".join(text_parts)
        except ImportError:
            raise RuntimeError("هذا الملف يبدو أنه صورة ممسوحة. يجب تثبيت: pip install PyMuPDF")
        except Exception as e:
            raise RuntimeError(f"فشل قراءة الـ PDF كصورة: {e}")

    return text
# ============================================================
#  تحليل النص واستخراج الحقول
# ============================================================
def _normalize_date(date_str):
    """يحوّل التاريخ إلى ISO (YYYY-MM-DD)."""
    if not date_str:
        return None
    s = str(date_str).strip()
    # 12/05/2026 أو 2026-05-12
    m = re.search(r"(\d{1,4})\s*[\-/\.]\s*(\d{1,2})\s*[\-/\.]\s*(\d{1,4})", s)
    if m:
        try:
            a, b, c = m.group(1), m.group(2), m.group(3)
            if len(a) == 4:
                y, mo, d = int(a), int(b), int(c)
            else:
                d, mo, y = int(a), int(b), int(c)
                if y < 100:
                    y += 2000
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except (ValueError, IndexError):
            pass
    return None


def _parse_amount(text, pattern):
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", "").strip())
        except (ValueError, IndexError):
            return 0.0
    return 0.0


def _parse_invoice_text(text):
    """يحلّل نص الفاتورة ويستخرج الحقول."""
    if not text:
        return {}

    # تطبيع النص
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)

    result = {}

    # ---- رقم الفاتورة ----
    m = re.search(
        r"(?:Invoice\s*(?:No\.?|Number|#)|فاتورة\s*رقم|رقم\s*الفاتورة)"
        r"\s*[:\-]?\s*([A-Z0-9\-_/]+)",
        text, re.IGNORECASE
    )
    if m:
        result["invoice_number"] = m.group(1).strip()

    # ---- تاريخ الإصدار ----
    m = re.search(
        r"(?:Issue\s*Date|Invoice\s*Date|Date|"
        r"تاريخ\s*الإصدار|تاريخ\s*الفاتورة|التاريخ)"
        r"\s*[:\-]?\s*(\d{1,4}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
        text, re.IGNORECASE
    )
    if m:
        normalized = _normalize_date(m.group(1))
        if normalized:
            result["issue_date"] = normalized

    # ---- المبلغ قبل الضريبة ----
    subtotal = _parse_amount(
        text,
        r"(?:Subtotal|Sub-total|Total\s*Before\s*Tax|"
        r"المجموع\s*قبل\s*الضريبة|المبلغ\s*قبل\s*الضريبة)"
        r"\s*[:\-]?\s*(?:AED|Dhs?|د\.إ)?\s*([\d,]+\.?\d*)"
    )

    # ---- الضريبة ----
    vat = _parse_amount(
        text,
        r"(?:VAT|Tax|V\.A\.T|"
        r"ضريبة\s*القيمة\s*المضافة|الضريبة|ضريبة)"
        r"\s*(?:\(?5%\)?)?\s*[:\-]?\s*(?:AED|Dhs?|د\.إ)?\s*([\d,]+\.?\d*)"
    )

    # ---- الإجمالي ----
    total = _parse_amount(
        text,
        r"(?:Total\s*Amount|Grand\s*Total|Total|"
        r"الإجمالي|المجموع\s*الكلي|إجمالي\s*الفاتورة)"
        r"\s*[:\-]?\s*(?:AED|Dhs?|د\.إ)?\s*([\d,]+\.?\d*)"
    )

    # تصحيح الناقص
    if total > 0 and subtotal == 0 and vat == 0:
        subtotal = round(total / 1.05, 2)
        vat = round(total - subtotal, 2)
    elif subtotal > 0 and vat == 0:
        vat = round(subtotal * 0.05, 2)
        total = round(subtotal + vat, 2)

    result["amount"] = subtotal
    result["vat_amount"] = vat
    result["total_amount"] = total

    return result


# ============================================================
#  الدالة الرئيسية
# ============================================================
def extract_invoice_data(file_path: str, suppliers=None):
    """
    يقرأ فاتورة ويستخرج بياناتها + يحاول مطابقة المورد.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        # استخراج النص
        if ext == ".pdf":
            text = _extract_text_from_pdf(file_path)
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"):
            text = _extract_text_from_image(file_path)
        else:
            return {"error": f"نوع الملف غير مدعوم: {ext}"}

        if not text or len(text.strip()) < 20:
            return {
                "error": "لم يُستخرج نص كافٍ من الفاتورة",
                "raw_text": text[:500] if text else "",
            }

        # تحليل
        data = _parse_invoice_text(text)

        # محاولة مطابقة المورد
        if suppliers:
            text_lower = text.lower()
            text_arabic = text

            for s in suppliers:
                # اسم إنجليزي
                if s.company_name_en and len(s.company_name_en) > 4:
                    if s.company_name_en.lower() in text_lower:
                        data["supplier_id"] = s.id
                        data["supplier_name"] = s.company_name_ar
                        data["match_method"] = "name_en"
                        break
                # اسم عربي
                if s.company_name_ar and len(s.company_name_ar) > 4:
                    if s.company_name_ar in text_arabic:
                        data["supplier_id"] = s.id
                        data["supplier_name"] = s.company_name_ar
                        data["match_method"] = "name_ar"
                        break
                # TRN
                if s.trn and s.trn in text:
                    data["supplier_id"] = s.id
                    data["supplier_name"] = s.company_name_ar
                    data["match_method"] = "trn"
                    break
                # رقم الرخصة
                if s.trade_license_no and s.trade_license_no in text:
                    data["supplier_id"] = s.id
                    data["supplier_name"] = s.company_name_ar
                    data["match_method"] = "license"
                    break

        data["raw_text"] = text[:5000]
        return data

    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        import traceback
        return {
            "error": f"خطأ: {e}",
            "traceback": traceback.format_exc()[:1000],
        }