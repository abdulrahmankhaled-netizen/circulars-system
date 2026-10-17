"""نماذج طلبات المعدات."""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, DateField,
    IntegerField, FieldList, FormField, SubmitField, HiddenField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange

from app.core.constants import PRIORITIES


def _equipment_choices():
    from app.core.constants import EQUIPMENT_TYPES
    return [(eq["key"], f"{eq['name_ar']} ({eq.get('name_en', '')})")
            for eq in EQUIPMENT_TYPES]


class RequestItemForm(FlaskForm):
    """نموذج بند واحد (سطر واحد في الطلب)."""
    class Meta:
        csrf = False  # الـ CSRF على مستوى الـ parent form

    equipment_key = SelectField(
        "نوع المعدة", choices=[], validators=[DataRequired()]
    )
    quantity = IntegerField(
        "الكمية", default=1,
        validators=[DataRequired(), NumberRange(min=1, max=100)],
    )
    notes = StringField("ملاحظات", validators=[Optional(), Length(max=200)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipment_key.choices = _equipment_choices()


class EquipmentRequestForm(FlaskForm):
    """النموذج الكامل للطلب."""

    # ============ البيانات الأساسية ============
    title = StringField(
        "عنوان الطلب",
        validators=[DataRequired(), Length(3, 200)],
    )
    department = StringField(
        "القسم",
        validators=[Optional(), Length(max=80)],
    )
    priority = SelectField(
        "الأولوية",
        choices=[(p[0], p[1]) for p in PRIORITIES],
        default="normal",
    )

    # ============ الموقع والمدة ============
    client_entity = StringField(
        "الجهة",
        validators=[Optional(), Length(max=150)],
    )
    region = StringField(
        "المنطقة",
        validators=[Optional(), Length(max=120)],
    )
    location = StringField(
        "الموقع التفصيلي",
        validators=[Optional(), Length(max=255)],
    )
    needed_from = DateField("من تاريخ", validators=[Optional()])
    needed_until = DateField("إلى تاريخ", validators=[Optional()])

    # ============ السبب والملاحظات ============
    reason = TextAreaField("سبب الطلب", validators=[Optional()])

    # ============ البنود ============
    items = FieldList(FormField(RequestItemForm), min_entries=1, max_entries=20)

    submit = SubmitField("حفظ")


class RequestActionForm(FlaskForm):
    """نموذج إجراء (submit/approve/reject...)"""
    action = HiddenField(validators=[DataRequired()])
    comment = TextAreaField("التعليق", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("تنفيذ")