from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, PasswordField, SubmitField, BooleanField,
                     TextAreaField, SelectField, HiddenField)
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from models import User


class RegistrationForm(FlaskForm):
    username         = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email            = StringField('Email',    validators=[DataRequired(), Email()])
    password         = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit           = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken. Please choose a different one.')


class LoginForm(FlaskForm):
    email    = StringField('Email',    validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit   = SubmitField('Login')


class BlogForm(FlaskForm):
    title    = StringField('Title',    validators=[DataRequired(), Length(max=200)])
    content  = TextAreaField('Content', validators=[DataRequired()])   # Quill fills this via hidden input
    cover_image = FileField('Cover Image', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Images only!')])
    category = SelectField('Category', coerce=int)
    tags     = StringField('Tags', validators=[Optional()],
                           description='Comma-separated tags, e.g. python, flask, web')
    submit   = SubmitField('Publish Post')


class CommentForm(FlaskForm):
    content   = TextAreaField('Comment',   validators=[DataRequired()])
    parent_id = HiddenField('Parent ID')   # for nested replies
    submit    = SubmitField('Post Comment')


class UpdateProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email    = StringField('Email',    validators=[DataRequired(), Email()])
    bio      = TextAreaField('Bio',    validators=[Length(max=500)])
    picture  = FileField('Update Profile Picture',
                         validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'],
                                                 'Images only!')])
    submit   = SubmitField('Update Profile')

    def __init__(self, original_username, original_email, *args, **kwargs):
        super(UpdateProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email    = original_email

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is taken. Please choose a different one.')

class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm New Password',
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')
