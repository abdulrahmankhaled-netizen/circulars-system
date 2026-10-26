"""نماذج الفواتير."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, SelectField, DateField, FloatField,
    TextAreaField, SubmitField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from datetime import date


class InvoiceForm(FlaskForm):
    invoice_type = SelectField(
        "نوع الفاتورة",
        choices=[
            ("supplier", "فاتورة مورد (ندفعها)"),
            ("customer", "فاتورة عميل (نستلمها)"),
        ],
        default="supplier",
    )

    invoice_number = StringField(
        "رقم الفاتورة", validators=[DataRequired(), Length(3, 60)]
    )

    # المورد (للفاتورة الواردة)
    supplier_id = SelectField(
        "المورد", coerce=int, validators=[Optional()]
    )

    # العميل (للفاتورة الصادرة)
    customer_name = StringField(
        "اسم العميل", validators=[Optional(), Length(max=200)]
    )
    customer_phone = StringField(
        "هاتف العميل", validators=[Optional(), Length(max=40)]
    )

    # الارتباطات
    contract_id = SelectField(
        "العقد", coerce=int, validators=[Optional()]
    )
    
    # ⭐ تم جعل المهمة إلزامية (DataRequired بدلاً من Optional)
    mission_id = SelectField(
        "المهمة", coerce=int, validators=[Optional()]
    )

    # التواريخ
    issue_date = DateField(
        "تاريخ الإصدار", validators=[Optional()], default=date.today
    )
    due_date = DateField("تاريخ الاستحقاق", validators=[Optional()])

    # المبالغ
    amount = FloatField(
        "المبلغ (قبل الضريبة)",
        validators=[DataRequired(), NumberRange(min=0)],
        default=0.0,
    )
    vat_amount = FloatField(
        "الضريبة (5%)",
        validators=[Optional(), NumberRange(min=0)],
        default=0.0,
    )
    total_amount = FloatField(
        "الإجمالي",
        validators=[Optional(), NumberRange(min=0)],
        default=0.0,
    )

    status = SelectField(
        "الحالة",
        choices=[
            ("draft", "مسودة"),
            ("submitted", "مُقدّمة"),
            ("approved", "معتمدة"),
            ("paid", "مدفوعة"),
            ("disputed", "متنازع عليها"),
            ("cancelled", "ملغاة"),
        ],
        default="draft",
    )

    # المرفق
    pdf_file = FileField(
        "نسخة الفاتورة (PDF)",
        validators=[Optional(), FileAllowed(["pdf", "png", "jpg", "jpeg"])],
    )

    notes = TextAreaField("ملاحظات", validators=[Optional()])

    submit = SubmitField("حفظ")