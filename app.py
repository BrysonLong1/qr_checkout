from flask import Flask, render_template, request, redirect, url_for, flash, abort, render_template_string
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from urllib.parse import quote_plus
import stripe, qrcode, io, base64, os   # <-- fixed import stripe
from datetime import datetime
from pytz import timezone

from forms import LoginForm, RegisterForm, TicketForm
from models import db, User, Ticket
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config.from_pyfile('config.py')  # must include SECRET_KEY

# Init extensions (AFTER app is created)
db.init_app(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
app.jinja_env.globals['csrf_token'] = generate_csrf

login_manager = LoginManager(app)
login_manager.login_view = 'login'

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ----- Stripe Connect blueprint (single source of truth) -----
from connect_routes import connect_bp
app.register_blueprint(connect_bp)
csrf.exempt(connect_bp)  # allow JS POSTs to /api/connect/*

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------
# Auth
# ---------------------------
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

# ---------------------------
# Ticket Dashboard (creator adds up to 5 tickets)
# ---------------------------
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    form = TicketForm()
    tickets = Ticket.query.filter_by(user_id=current_user.id).all()

    if form.validate_on_submit():
        if len(tickets) >= 5:
            flash("You can only add up to 5 tickets.")
        else:
            t = Ticket(name=form.name.data, price=form.price.data, user_id=current_user.id)
            db.session.add(t)
            db.session.commit()
            flash("Ticket added.")
        return redirect(url_for('dashboard'))

    return render_template('dashboard.html', form=form, tickets=tickets)

# ---------------------------
# Generate QR for selected ticket
# ---------------------------
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    tickets = Ticket.query.filter_by(user_id=current_user.id).all()
    has_tickets = len(tickets) > 0

    if request.method == 'POST' and 'ticket_id' in request.form:
        try:
            ticket_id = int(request.form.get('ticket_id'))
        except (TypeError, ValueError):
            flash("Please select a valid ticket.")
            return redirect(url_for('index'))

        sel = Ticket.query.get_or_404(ticket_id)
        if sel.user_id != current_user.id:
            flash("Not your ticket.")
            return redirect(url_for('index'))

        SERVICE_FEE = 4.50  # flat platform fee
        total_price = round(float(sel.price) + SERVICE_FEE, 2)

        success_url = (
            "https://teameventlock.com/success"
            f"?ticket={quote_plus(sel.name)}&price={total_price}"
        )

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': sel.name},
                    'unit_amount': int(total_price * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=request.host_url,
        )

        qr = qrcode.make(session.url)
        buffered = io.BytesIO()
        qr.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return render_template('qrcode.html', img_data=img_str, ticket_name=sel.name, total_price=total_price)

    return render_template("index.html", tickets=tickets, has_tickets=has_tickets, service_fee=4.5)

# ---------------------------
# Payouts page (single definition)
# ---------------------------
@app.route('/payouts')
@login_required
def payouts():
    return render_template_string("""
      <h2>Connect to Stripe for payouts</h2>
      <button id="connectBtn">Set up payouts</button>
      <script>
      document.getElementById('connectBtn').onclick = async () => {
        const r = await fetch('/api/connect/create-account', { method:'POST' });
        if (!r.ok) { alert('Failed to start onboarding'); return; }
        const j = await r.json();
        window.location = j.url; // go to Stripe onboarding
      };
      </script>
    """)

# ---------------------------
# Misc
# ---------------------------
@app.route('/ticket/<int:ticket_id>')
def ticket_scan(ticket_id):
    t = Ticket.query.get_or_404(ticket_id)
    return f"Scanned ticket: {t.name} - ${t.price}"

@app.route('/success')
def success():
    eastern = timezone('US/Eastern')
    ticket = request.args.get('ticket', default='Unknown Ticket')
    price = request.args.get('price', default='0.00')
    timestamp = datetime.now(eastern).strftime('%B %d, %Y at %I:%M %p')
    print("SUCCESS ROUTE HIT", ticket, price)
    return render_template('success.html', ticket=ticket, price=price, timestamp=timestamp)

@app.route('/_debug')
def debug_check():
    return "✔ App is running"

@app.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
@login_required
def delete_ticket(ticket_id):
    t = Ticket.query.get_or_404(ticket_id)
    if t.user_id != current_user.id:
        abort(403)
    db.session.delete(t)
    db.session.commit()
    flash('Ticket deleted.')
    return redirect(url_for('dashboard'))

# ---------------------------
# Local dev
# ---------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
