"""نماذج العقود."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, SelectField, DateField, FloatField,
    TextAreaField, BooleanField, SubmitField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class ContractForm(FlaskForm):
    # ============ المورد ============
    supplier_id = SelectField(
        "المورد", coerce=int, validators=[DataRequired()]
    )

    contract_number = StringField(
        "رقم العقد", validators=[DataRequired(), Length(3, 60)]
    )

    # ============ الجهة والمنطقة ============
    client_entity = StringField(
        "الجهة (عربي)", validators=[Optional(), Length(max=150)]
    )
    client_entity_en = StringField(
        "الجهة (إنجليزي)", validators=[Optional(), Length(max=150)]
    )
    region = StringField(
        "المنطقة (عربي)", validators=[Optional(), Length(max=120)]
    )
    region_en = StringField(
        "المنطقة (إنجليزي)", validators=[Optional(), Length(max=120)]
    )
    location_keywords = TextAreaField(
        "كلمات الموقع المفتاحية (افصل بفاصلة)",
        validators=[Optional()],
    )

    # ============ المدد ============
    start_date = DateField("تاريخ البداية", validators=[Optional()])
    end_date = DateField("تاريخ الانتهاء", validators=[Optional()])

    # ============ القيمة ============
    value = FloatField(
        "قيمة العقد",
        validators=[Optional(), NumberRange(min=0)],
        default=0.0,
    )
    currency = SelectField(
        "العملة",
        choices=[("AED", "AED"), ("USD", "USD")],
        default="AED",
    )
    value_period = SelectField(
        "فترة التسعير",
        choices=[
            ("per_mission", "لكل مهمة"),
            ("monthly", "شهرياً"),
            ("quarterly", "كل 3 أشهر"),
            ("semi_annual", "كل 6 أشهر"),
            ("annual", "سنوياً"),
        ],
        default="per_mission",
    )
    payment_terms = StringField(
        "شروط الدفع", validators=[Optional(), Length(max=200)]
    )

    # ============ المرفق ============
    signed_document = FileField(
        "نسخة العقد الموقّعة",
        validators=[Optional(), FileAllowed(["pdf", "doc", "docx", "png", "jpg"])],
    )

    # ============ الحالة ============
    status = SelectField(
        "الحالة",
        choices=[
            ("draft", "مسودة"),
            ("pending_signature", "بانتظار التوقيع"),
            ("active", "نشط"),
            ("expiring", "قارب الانتهاء"),
            ("expired", "منتهي"),
            ("terminated", "ملغى"),
        ],
        default="draft",
    )

    notes = TextAreaField("ملاحظات", validators=[Optional()])

    submit = SubmitField("حفظ")