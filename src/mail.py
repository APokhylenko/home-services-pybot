import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from settings import FROM_EMAIL, TO_EMAIL, SENDGRID_API_KEY, SENDGRID_TEMPLATE_ID

logger = logging.getLogger(__name__)


def send_email(subject, body):
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=TO_EMAIL,
        subject=subject,
        html_content=body
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        logger.exception(e)


def send_counters_email(template_data):
    """Send email via Sendgrid."""
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=TO_EMAIL,
        subject='Новые данные по коммунальным услугам',
        html_content='+'
    )

    message.dynamic_template_data = template_data
    message.template_id = SENDGRID_TEMPLATE_ID
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        logger.exception(e)
