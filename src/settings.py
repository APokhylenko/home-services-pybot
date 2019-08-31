import os

from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DB_URL")
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
RENTER_USERNAME = os.getenv("RENTER")
OWNER_USERNAME = os.getenv("OWNER")
FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL = os.getenv("TO_EMAIL")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_TEMPLATE_ID = os.getenv("SENDGRID_TEMPLATE_ID")
HEATING_LOGIN = os.getenv("HEATING_LOGIN")
HEATING_PASSWORD = os.getenv("HEATING_PASSWORD")
HEATING_LOGIN_API = os.getenv("HEATING_LOGIN_API")
HEATING_BILL_API = os.getenv("HEATING_BILL_API")
HEATING_PROVIDER_ID = os.getenv("HEATING_PROVIDER_ID")
