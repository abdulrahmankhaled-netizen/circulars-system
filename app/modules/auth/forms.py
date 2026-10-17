"""نماذج المصادقة."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    username = StringField("اسم المستخدم", validators=[DataRequired(), Length(3, 80)])
    password = PasswordField("كلمة المرور", validators=[DataRequired()])
    remember = BooleanField("تذكرني")
    submit = SubmitField("تسجيل الدخول")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("كلمة المرور الحالية", validators=[DataRequired()])
    new_password = PasswordField(
        "كلمة المرور الجديدة",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    confirm_password = PasswordField(
        "تأكيد كلمة المرور الجديدة",
        validators=[DataRequired()],
    )
    submit = SubmitField("تغيير")