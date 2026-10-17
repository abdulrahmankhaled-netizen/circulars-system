"""نماذج المستخدمين."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length, EqualTo


class UserForm(FlaskForm):
    username = StringField("اسم المستخدم", validators=[DataRequired(), Length(3, 80)])
    full_name = StringField("الاسم الكامل", validators=[DataRequired(), Length(2, 150)])
    email = StringField("البريد الإلكتروني", validators=[Optional(), Email()])
    phone = StringField("الهاتف", validators=[Optional(), Length(max=40)])
    department = StringField("القسم", validators=[Optional(), Length(max=80)])

    role_id = SelectField("الدور", coerce=int, validators=[DataRequired()])
    is_active = BooleanField("نشط", default=True)

    password = PasswordField(
        "كلمة المرور", validators=[Optional(), Length(min=6, max=128)]
    )
    password_confirm = PasswordField(
        "تأكيد كلمة المرور",
        validators=[Optional(), EqualTo("password", message="كلمتا المرور غير متطابقتين")],
    )

    submit = SubmitField("حفظ")