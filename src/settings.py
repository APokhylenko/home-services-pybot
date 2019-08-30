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

MEDIA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media')
