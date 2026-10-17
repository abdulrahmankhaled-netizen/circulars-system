"""نماذج الموردين."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, SelectField, DateField, BooleanField,
    TextAreaField, SubmitField,
)
from wtforms.validators import DataRequired, Email, Optional, Length


class SupplierForm(FlaskForm):
    company_name_ar = StringField("اسم الشركة (عربي)",
                                   validators=[DataRequired(), Length(2, 200)])
    company_name_en = StringField("اسم الشركة (إنجليزي)",
                                   validators=[Optional(), Length(max=200)])

    trade_license_no = StringField("رقم الرخصة التجارية",
                                    validators=[DataRequired(), Length(2, 80)])
    trade_license_expiry = DateField("تاريخ انتهاء الرخصة", validators=[Optional()])
    trade_license_file = FileField("نسخة الرخصة التجارية",
                                    validators=[Optional(), FileAllowed(["pdf", "png", "jpg", "jpeg"])])
    transport_permit_no = StringField("رقم تصريح النقل البري",
                                       validators=[Optional(), Length(max=80)])

    contact_person = StringField("الشخص المسؤول",
                                  validators=[Optional(), Length(max=120)])
    phone = StringField("الهاتف", validators=[Optional(), Length(max=40)])
    email = StringField("البريد الإلكتروني", validators=[Optional(), Email()])
    address = StringField("العنوان", validators=[Optional(), Length(max=255)])

    bank_name = StringField("اسم البنك", validators=[Optional(), Length(max=120)])
    iban = StringField("رقم IBAN", validators=[Optional(), Length(max=60)])

    vat_registered = BooleanField("مسجل في ضريبة القيمة المضافة (VAT)")
    trn = StringField("الرقم الضريبي (TRN)",
                       validators=[Optional(), Length(max=15)])
    tax_certificate_expiry = DateField("تاريخ انتهاء الشهادة الضريبية",
                                        validators=[Optional()])
    tax_certificate_file = FileField("نسخة الشهادة الضريبية",
                                      validators=[Optional(), FileAllowed(["pdf", "png", "jpg", "jpeg"])])

    authorized_signatory_name = StringField("اسم المفوض بالتوقيع",
                                             validators=[Optional(), Length(max=120)])
    authorized_signatory_title = StringField("صفة المفوض بالتوقيع",
                                              validators=[Optional(), Length(max=120)])
    signature_file = FileField("صورة التوقيع المعتمد",
                                validators=[Optional(), FileAllowed(["png", "jpg", "jpeg"])])

    status = SelectField("الحالة",
                          choices=[
                              ("active", "نشط"),
                              ("suspended", "موقوف"),
                              ("blacklisted", "محظور"),
                          ],
                          default="active")
    notes = TextAreaField("ملاحظات", validators=[Optional()])

    submit = SubmitField("حفظ")