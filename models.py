# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime


db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Stripe Connect
    stripe_account_id = db.Column(db.String(64), index=True)
    charges_enabled   = db.Column(db.Boolean, default=False)
    details_submitted = db.Column(db.Boolean, default=False)

    # NEW
    email_confirmed_at = db.Column(db.DateTime, index=True, nullable=True)

    @property
    def is_confirmed(self) -> bool:
        return self.email_confirmed_at is not None
    fee_percent = db.Column(db.Float, nullable=False, server_default="12.0")

    def __repr__(self):
        return f"<User {self.email}>"

class Ticket(db.Model):
    __tablename__ = "ticket"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # optional; if null, fall back to user's fee_percent
    fee_percent = db.Column(db.Float, nullable=True)

    user = db.relationship("User", backref="tickets")

    def __repr__(self):
        return f"<Ticket {self.name} - ${self.price:.2f}>"
