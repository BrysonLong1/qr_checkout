from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email, EqualTo, Length

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[
        InputRequired(message="Email is required"),
        Email(message="Enter a valid email")
    ])
    password = PasswordField('Password', validators=[
        InputRequired(message="Password is required"),
        Length(min=6, message="Password must be at least 6 characters")
    ])
    confirm = PasswordField('Confirm Password', validators=[
        InputRequired(message="Please confirm your password"),
        EqualTo('password', message="Passwords must match")
    ])
    submit = SubmitField('Create Account')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        InputRequired(message="Email is required"),
        Email(message="Enter a valid email")
    ])
    password = PasswordField('Password', validators=[
        InputRequired(message="Password is required")
    ])
    submit = SubmitField('Log In')