from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # --- Stripe Connect fields ---
    stripe_account_id = db.Column(db.String(64), index=True)          # e.g. "acct_1ABCDEF..."
    charges_enabled   = db.Column(db.Boolean, default=False)          # optional: payouts readiness
    details_submitted = db.Column(db.Boolean, default=False)          # optional: onboarding done

    def __repr__(self):
        return f"<User {self.email}>"

class Ticket(db.Model):
    __tablename__ = "ticket"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    user = db.relationship("User", backref="tickets")

    def __repr__(self):
        return f"<Ticket {self.name} - ${self.price:.2f}>"
