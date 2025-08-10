from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DecimalField, SubmitField
from wtforms.validators import InputRequired, Email, EqualTo, Length, DataRequired, NumberRange

# --------------------
# Registration Form
# --------------------
class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[
        InputRequired(message="Email is required"),
        Email(message="Enter a valid email")
    ])
    password = PasswordField('Password', validators=[
        InputRequired(message="Password is required"),
        Length(min=8, message="Password must be at least 8 characters")
    ])
    confirm = PasswordField('Confirm Password', validators=[
        InputRequired(message="Please confirm your password"),
        EqualTo('password', message="Passwords must match")
    ])
    submit = SubmitField('Create Account')

# --------------------
# Login Form
# --------------------
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        InputRequired(message="Email is required"),
        Email(message="Enter a valid email")
    ])
    password = PasswordField('Password', validators=[
        InputRequired(message="Password is required")
    ])
    submit = SubmitField('Log In')

# --------------------
# Ticket Creation Form
# --------------------
class TicketForm(FlaskForm):
    name = StringField('Ticket Name', validators=[DataRequired()])
    price = DecimalField('Ticket Price ($)', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Add Ticket')
