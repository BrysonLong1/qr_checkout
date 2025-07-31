from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import stripe, qrcode, io, base64, os
from datetime import datetime
from forms import LoginForm, RegisterForm
from models import db, User

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config.from_pyfile('config.py')

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered')
            return redirect(url_for('register'))

        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(email=form.email.data, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    DRINKS = {
        "Tequila": 8.00,
        "Shirley Temple": 3.50,
        "Can beer/seltzers": 5.00,
        "Heineken": 5.95,
        "Liqueurs/Other": 8.00,
        "White Claw": 7.75,
        "Michelob ultra": 5.00,
        "Red Bull": 6.00,
        "Ray’s Rum Punch": 13.00,
        "Strawberry Vodka Lemonade": 8.00,
        "Deer Park Bottled Water": 2.00,
        "Corona Extra": 5.00,
        "Bud Light": 5.00,
        "Rum": 7.00,
        "Jamaican Mule": 13.00,
        "Housemade Juices and Lemonades": 5.00
    }

    SERVICE_FEE = 3.20

    if request.method == 'POST':
        drink = request.form['drink']
        tip = float(request.form.get('tip', 0))
        base_price = DRINKS.get(drink, 0)
        total_price = round(base_price + SERVICE_FEE + tip, 2)

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': drink},
                    'unit_amount': int(total_price * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.host_url + 'success?drink=' + drink + '&price=' + str(total_price),
            cancel_url=request.host_url,
        )

        qr = qrcode.make(session.url)
        buffered = io.BytesIO()
        qr.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return render_template('qrcode.html', img_data=img_str)

    return render_template('index.html', drinks=DRINKS, service_fee=SERVICE_FEE)

@app.route('/success')
@login_required
def success():
    drink = request.args.get('drink')
    price = request.args.get('price')
    return render_template('success.html', drink=drink, price=price)

# Start the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)