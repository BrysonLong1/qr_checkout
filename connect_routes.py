# connect_routes.py
import os
from urllib.parse import urlencode

import stripe
from flask import Blueprint, jsonify, request, redirect
from flask_login import login_required, current_user

from models import db  # import once at top

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = os.getenv("PLATFORM_BASE_URL", "http://localhost:5000")

# export this name (app.py imports connect_bp)
connect_bp = Blueprint("connect_bp", __name__)


# Helper: ensure current_user has a connected account; create if missing
def _ensure_account_id_for(user):
    acct_id = getattr(user, "stripe_account_id", None)
    if not acct_id:
        acct = stripe.Account.create(
            type="express",
            email=user.email,
            capabilities={"transfers": {"requested": True}},
            metadata={"user_id": str(user.id)},
        )
        user.stripe_account_id = acct.id
        db.session.commit()
        acct_id = acct.id
    return acct_id


# 1) Create/ensure account, then generate onboarding link
#    POST /api/connect/create-account
@connect_bp.post("/api/connect/create-account")
@login_required
def create_account():
    account_id = _ensure_account_id_for(current_user)

    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{BASE_URL}/connect/reauth?{urlencode({'account_id': account_id})}",
        return_url=f"{BASE_URL}/connect/return?{urlencode({'account_id': account_id})}",
        type="account_onboarding",
    )
    return jsonify({"account_id": account_id, "url": link.url})


# 2) Refresh link Stripe can send the user to if the flow expires
#    GET /connect/reauth?account_id=acct_xxx
@connect_bp.get("/connect/reauth")
@login_required
def reauth():
    account_id = request.args.get("account_id") or _ensure_account_id_for(current_user)
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{BASE_URL}/connect/reauth?{urlencode({'account_id': account_id})}",
        return_url=f"{BASE_URL}/connect/return?{urlencode({'account_id': account_id})}",
        type="account_onboarding",
    )
    return redirect(link.url)


# 3) Return target after onboarding completes
#    GET /connect/return?account_id=acct_xxx
@connect_bp.get("/connect/return")
@login_required
def connect_return():
    account_id = request.args.get("account_id") or getattr(current_user, "stripe_account_id", None)
    if not account_id:
        return redirect("/payouts")

    acct = stripe.Account.retrieve(account_id)

    # Optional: persist useful flags on your user record
    # Add these columns to your User model if you want to store:
    #   charges_enabled = db.Column(db.Boolean, default=False)
    #   details_submitted = db.Column(db.Boolean, default=False)
    try:
        if hasattr(current_user, "charges_enabled"):
            current_user.charges_enabled = bool(acct.charges_enabled)
        if hasattr(current_user, "details_submitted"):
            current_user.details_submitted = bool(acct.details_submitted)
        db.session.commit()
    except Exception:
        db.session.rollback()

    # back to your payouts page (or wherever)
    return redirect("/payouts")


# 4) Express Dashboard quick link for the connected account
#    POST /api/connect/dashboard
@connect_bp.post("/api/connect/dashboard")
@login_required
def express_dashboard():
    account_id = _ensure_account_id_for(current_user)
    login_link = stripe.Account.create_login_link(account_id)
    return jsonify({"url": login_link.url})


# 5) (Optional) Webhook to track account state changes
#    POST /stripe/webhook
@connect_bp.post("/stripe/webhook")
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")  # set in Dashboard

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError:
        return "Invalid signature", 400

    if event["type"] == "account.updated":
        acct = event["data"]["object"]
        # Example: update the user if you store the acct->user relationship
        # user = User.query.filter_by(stripe_account_id=acct["id"]).first()
        # if user and hasattr(user, "charges_enabled"):
        #     user.charges_enabled = bool(acct.get("charges_enabled"))
        #     db.session.commit()
        print("Account updated:", acct["id"])

    return "", 200
