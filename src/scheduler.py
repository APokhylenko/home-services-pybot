from datetime import datetime

import telegram
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import utc

import models
from mail import send_email
from settings import DB_URL, TELEGRAM_TOKEN, RENTER_USERNAME

jobstores = {
    'default': SQLAlchemyJobStore(url=DB_URL)
}
scheduler = BackgroundScheduler(jobstores=jobstores, timezone=utc)


def ask_for_counters_data():
    """Send message to renter reminding to submit new counters data."""
    user = models.User.get_user_by_username(RENTER_USERNAME)

    if not user or not user.chat_id:
        return

    counters_data_this_month = models.Counters.get_current_month_counters_data(user.chat_id)

    if not counters_data_this_month:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        bot.send_message(chat_id=user.chat_id, text="Привет-привет!)")
        bot.send_message(chat_id=user.chat_id, text="Отправь мне пожалуйста показания счетчиков) заранее спасибо <3")


def mark_as_paid():
    """Automatically mark every month as paid. Send email with notification."""
    current_month_number = datetime.now().month
    models.FlatPayment.mark_as_paid_or_unpaid(current_month_number)
    current_month = datetime.now().strftime("%B")
    send_email(f'{current_month} отмечен как оплаченный.',
               'Для отмены <b>Оплачено > выбрать месяц, который не оплачен </b>')
