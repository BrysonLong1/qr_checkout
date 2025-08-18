import os
from urllib.parse import urlencode
from dotenv import load_dotenv

import stripe
from flask import Blueprint, jsonify, request, redirect
from flask_login import login_required, current_user
from models import db

# Load .env for local/dev; in production you also set envs via systemd
load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
BASE_URL = os.getenv("PLATFORM_BASE_URL", "https://teameventlock.com")

connect_bp = Blueprint("connect_bp", __name__)

def _ensure_account_id_for(user):
    """
    Ensure the user has a Stripe Express account and that both capabilities are requested.
    """
    acct_id = getattr(user, "stripe_account_id", None)

    if not acct_id:
        # New account: request BOTH capabilities up-front (normal marketplace flow)
        acct = stripe.Account.create(
            type="express",
            country="US",
            email=user.email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            metadata={"user_id": str(user.id)},
        )
        user.stripe_account_id = acct.id
        db.session.commit()
        return acct.id

    # Existing account: re-request capabilities if not active or pending
    acct = stripe.Account.retrieve(acct_id)
    caps = getattr(acct, "capabilities", {}) or {}
    needs_card = caps.get("card_payments") not in ("active", "pending")
    needs_transfers = caps.get("transfers") not in ("active", "pending")
    if needs_card or needs_transfers:
        stripe.Account.modify(
            acct_id,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
        )
    return acct_id


@connect_bp.get("/api/connect/health")
def connect_health():
    """Ping Stripe for a specific connected account and report readiness."""
    import stripe, os
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")  # platform key

    acct_id = request.args.get("acct")
    if not acct_id:
        return jsonify({"ok": False, "error": "Missing ?acct=acct_..." }), 400

    try:
        acct = stripe.Account.retrieve(acct_id)
        caps = getattr(acct, "capabilities", {}) or {}

        result = {
            "ok": bool(acct.charges_enabled and acct.payouts_enabled),
            "id": acct.id,
            "charges_enabled": bool(acct.charges_enabled),
            "payouts_enabled": bool(acct.payouts_enabled),
            "details_submitted": bool(getattr(acct, "details_submitted", False)),
            "capabilities": {
                "card_payments": caps.get("card_payments"),
                "transfers": caps.get("transfers"),
            },
            "currently_due": (getattr(getattr(acct, "requirements", None), "currently_due", None) or []),
        }
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

# Start onboarding (creates/ensures account, returns onboarding link)
@connect_bp.post("/api/connect/create-account")
@login_required
def create_account():
    try:
        account_id = _ensure_account_id_for(current_user)
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=f"{BASE_URL}/connect/reauth?{urlencode({'account_id': account_id})}",
            return_url=f"{BASE_URL}/connect/return?{urlencode({'account_id': account_id})}",
            type="account_onboarding",
        )
        return jsonify({"account_id": account_id, "url": link.url}), 200
    except stripe.error.StripeError as e:
        msg = getattr(e, "user_message", None) or str(e)
        print(f"[StripeError] {e}")
        return jsonify({"error": msg}), 400
    except Exception as e:
        print(f"[ConnectError] {e}")
        return jsonify({"error": str(e)}), 500


# If their link expired, generate a fresh one
@connect_bp.get("/connect/reauth")
@login_required
def reauth():
    try:
        account_id = request.args.get("account_id") or _ensure_account_id_for(current_user)
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=f"{BASE_URL}/connect/reauth?{urlencode({'account_id': account_id})}",
            return_url=f"{BASE_URL}/connect/return?{urlencode({'account_id': account_id})}",
            type="account_onboarding",
        )
        return redirect(link.url)
    except Exception as e:
        print(f"[ConnectReauthError] {e}")
        return redirect("/payouts")


# Land here after onboarding
@connect_bp.get("/connect/return")
@login_required
def connect_return():
    account_id = request.args.get("account_id") or getattr(current_user, "stripe_account_id", None)
    if not account_id:
        return redirect("/payouts")
    try:
        acct = stripe.Account.retrieve(account_id)
        # Persist helpful flags on the user record
        if hasattr(current_user, "stripe_account_id") and not current_user.stripe_account_id:
            current_user.stripe_account_id = acct.id
        if hasattr(current_user, "charges_enabled"):
            current_user.charges_enabled = bool(acct.get("charges_enabled"))
        if hasattr(current_user, "details_submitted"):
            current_user.details_submitted = bool(acct.get("details_submitted"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect("/payouts?onboard=done")

# Express Dashboard button (nice-to-have)
@connect_bp.post("/api/connect/dashboard")
@login_required
def express_dashboard():
    try:
        account_id = _ensure_account_id_for(current_user)
        login_link = stripe.Account.create_login_link(account_id)
        return jsonify({"url": login_link.url}), 200
    except Exception as e:
        print(f"[DashboardLinkError] {e}")
        return jsonify({"error": str(e)}), 400

@connect_bp.get("/api/connect/status")
@login_required
def connect_status():
    try:
        acct_id = getattr(current_user, "stripe_account_id", None)
        if not acct_id:
            return jsonify({"ready": False, "reason": "no_account"}), 200

        # If you persist flags on the user, trust them first:
        charges_ok = bool(getattr(current_user, "charges_enabled", False))
        details_ok = bool(getattr(current_user, "details_submitted", False))
        # Optionally double-check with Stripe to be extra sure:
        if not (charges_ok and details_ok):
            acct = stripe.Account.retrieve(acct_id)
            charges_ok = bool(acct.get("charges_enabled"))
            details_ok = bool(acct.get("details_submitted"))

        return jsonify({
            "ready": charges_ok and details_ok,
            "charges_enabled": charges_ok,
            "details_submitted": details_ok
        }), 200
    except Exception as e:
        print(f"[ConnectStatusError] {e}")
        return jsonify({"ready": False, "error": "status_check_failed"}), 200

# Webhook (optional) to monitor account updates
@connect_bp.post("/stripe/webhook")
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        return "Invalid", 400

    if event.get("type") == "account.updated":
        acct = event["data"]["object"]
        print(f"[Webhook] account.updated {acct.get('id')} charges_enabled={acct.get('charges_enabled')}")

    return "", 200
