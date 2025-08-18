import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.getenv("SECRET_KEY", "defaultsecret")

# Database
SQLALCHEMY_DATABASE_URI = (
    os.getenv("SQLALCHEMY_DATABASE_URI")
    or f"sqlite:///{os.path.join(BASE_DIR, 'users.db')}"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")  # must be sk_live_* or sk_test_*
PLATFORM_BASE_URL = os.getenv("PLATFORM_BASE_URL", "https://teameventlock.com")

# Email settings
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
MAIL_USE_TLS = True
MAIL_USERNAME = os.getenv("MAIL_USERNAME")  # your SMTP login
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")  # your SMTP password / app password
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "no-reply@teameventlock.com")

# Email confirmation security
SECURITY_CONFIRM_SALT = os.getenv("SECURITY_CONFIRM_SALT", "change-me")
CONFIRM_TOKEN_EXPIRATION = int(os.getenv("CONFIRM_TOKEN_EXPIRATION", 3600))  # 1 hour default
