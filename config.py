import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "defaultsecret")
SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
SQLALCHEMY_TRACK_MODIFICATIONS = False