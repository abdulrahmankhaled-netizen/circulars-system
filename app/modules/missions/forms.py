"""نماذج المهام."""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, SelectField, TextAreaField, FloatField,
    DateTimeLocalField, SubmitField, BooleanField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from datetime import datetime


def _equipment_choices():
    """يقرأ الأنواع من قاعدة البيانات، وإن كانت فارغة يقرأ من constants."""
    try:
        from app.modules.equipment.models import EquipmentType
        types = EquipmentType.query.filter_by(is_active=True)\
            .order_by(EquipmentType.sort_order, EquipmentType.name_ar).all()
        if types:
            return [(t.key, f"{t.name_ar} ({t.name_en or ''})".strip())
                    for t in types]
    except Exception:
        pass

    from app.core.constants import EQUIPMENT_TYPES
    return [(eq["key"], f"{eq['name_ar']} ({eq.get('name_en', '')})")
            for eq in EQUIPMENT_TYPES]


class MissionForm(FlaskForm):
    # ============ العقد ============
    contract_id = SelectField(
        "العقد", coerce=int, validators=[DataRequired()]
    )

    # ============ المعدة ============
    equipment_key = SelectField(
        "نوع المعدة", choices=[], validators=[DataRequired()]
    )

    # ============ الشبك (Impound) ============
    is_impound = BooleanField("المهمة حجز بالشبك", default=False)
    store_number = StringField(
        "رقم التخزين", validators=[Optional(), Length(max=80)]
    )
    job_order_id = StringField(
        "رقم أمر العمل (Job Order)",
        validators=[Optional(), Length(max=80)]
    )

    # ============ بيانات إضافية من Excel ============
    job_id_external = StringField(
        "Job ID (Excel)", validators=[Optional(), Length(max=80)]
    )
    payer_type = StringField(
        "نوع الدافع", validators=[Optional(), Length(max=50)]
    )
    requested_rec_type = StringField(
        "نوع المعدة المطلوب", validators=[Optional(), Length(max=120)]
    )
    actual_rec_type = StringField(
        "نوع المعدة الفعلي", validators=[Optional(), Length(max=120)]
    )
    toll_job_id = StringField(
        "رقم Toll Job", validators=[Optional(), Length(max=80)]
    )
    toll_amount = FloatField(
        "مبلغ Toll", validators=[Optional(), NumberRange(min=0)]
    )
    advisor = StringField(
        "المستشار (Advisor)", validators=[Optional(), Length(max=120)]
    )
    service_centre = StringField(
        "الورشة / Service Center", validators=[Optional(), Length(max=150)]
    )
    sub_status = StringField(
        "الحالة الفرعية", validators=[Optional(), Length(max=80)]
    )

    # ============ المركبة ============
    vehicle_plate = StringField(
        "رقم اللوحة", validators=[Optional(), Length(max=40)]
    )
    vehicle_make = StringField(
        "الشركة المصنعة", validators=[Optional(), Length(max=80)]
    )
    vehicle_model = StringField(
        "الموديل", validators=[Optional(), Length(max=80)]
    )
    vehicle_vin = StringField(
        "رقم الهيكل (VIN)", validators=[Optional(), Length(max=80)]
    )

    # ============ العميل ============
    customer_name = StringField(
        "اسم العميل", validators=[Optional(), Length(max=200)]
    )
    customer_phone = StringField(
        "هاتف العميل", validators=[Optional(), Length(max=40)]
    )

    # ============ الموقع ============
    pickup_location = StringField(
        "موقع الاستلام", validators=[Optional(), Length(max=255)]
    )
    drop_location = StringField(
        "موقع التسليم", validators=[Optional(), Length(max=255)]
    )
    region = StringField(
        "المنطقة", validators=[Optional(), Length(max=120)]
    )

    # ============ التاريخ ============
    mission_date = DateTimeLocalField(
        "تاريخ المهمة",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
        default=datetime.now,
    )

    # ============ السائق ============
    driver_name = StringField(
        "اسم السائق", validators=[Optional(), Length(max=120)]
    )
    driver_phone = StringField(
        "هاتف السائق", validators=[Optional(), Length(max=40)]
    )

    # ============ المالية ============
    cost = FloatField(
        "التكلفة (AED)",
        validators=[Optional(), NumberRange(min=0)],
        default=0.0,
    )
    revenue = FloatField(
        "الإيراد (AED)",
        validators=[Optional(), NumberRange(min=0)],
        default=0.0,
    )

    # ============ حالة الدفع ============
    supplier_payment_status = SelectField(
        "حالة الدفع للمورد",
        choices=[
            ("pending", "معلّق"),
            ("paid", "مدفوع"),
            ("cancelled", "ملغي"),
        ],
        default="pending",
    )
    customer_invoice_status = SelectField(
        "حالة الفاتورة للعميل",
        choices=[
            ("pending", "بانتظار الفاتورة"),
            ("invoiced", "مفوتر"),
            ("paid", "مدفوع"),
            ("cancelled", "ملغي"),
        ],
        default="pending",
    )

    # ============ الحالة ============
    status = SelectField(
        "الحالة",
        choices=[
            ("draft", "مسودة"),
            ("assigned", "مُعيّنة"),
            ("in_progress", "قيد التنفيذ"),
            ("completed", "مكتملة"),
            ("verified", "تم التحقق"),
            ("invoiced", "مفوترة"),
            ("paid", "مدفوعة"),
            ("failed", "فاشلة"),
            ("cancelled", "ملغاة"),
        ],
        default="draft",
    )

    # ============ الملاحظات ============
    notes = TextAreaField("ملاحظات", validators=[Optional()])
    completion_notes = TextAreaField("ملاحظات الإنجاز", validators=[Optional()])

    submit = SubmitField("حفظ")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipment_key.choices = _equipment_choices()