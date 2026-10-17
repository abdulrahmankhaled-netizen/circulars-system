"""نماذج المعدات والأسعار."""
from flask_wtf import FlaskForm
from wtforms import (
    SelectField, FloatField, StringField, BooleanField,
    TextAreaField, SubmitField, IntegerField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange


def _equipment_choices():
    """قائمة أنواع المعدات من قاعدة البيانات، أو من constants."""
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


class EquipmentPriceForm(FlaskForm):
    supplier_id = SelectField(
        "المورد", coerce=int, validators=[DataRequired()]
    )
    equipment_key = SelectField(
        "نوع المعدة", choices=[], validators=[DataRequired()]
    )

    unit_price = FloatField(
        "السعر (AED)",
        validators=[DataRequired(), NumberRange(min=0)],
        default=0.0,
    )

    notes = TextAreaField("ملاحظات", validators=[Optional()])
    is_active = BooleanField("مفعّل", default=True)

    submit = SubmitField("حفظ")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipment_key.choices = _equipment_choices()


class EquipmentTypeForm(FlaskForm):
    """نموذج إضافة/تعديل نوع معدة."""
    key = StringField(
        "المفتاح (بالإنجليزية)",
        validators=[Optional(), Length(max=80)],
    )
    name_ar = StringField(
        "الاسم (عربي)",
        validators=[DataRequired(), Length(2, 120)],
    )
    name_en = StringField(
        "الاسم (إنجليزي)",
        validators=[Optional(), Length(max=120)],
    )
    description = TextAreaField("وصف", validators=[Optional()])
    sort_order = IntegerField(
        "ترتيب العرض", validators=[Optional()], default=100
    )
    is_active = BooleanField("مفعّل", default=True)

    submit = SubmitField("حفظ")