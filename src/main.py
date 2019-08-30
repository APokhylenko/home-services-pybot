import calendar
import logging

import requests as r
from tabulate import tabulate
from telegram import ReplyKeyboardMarkup, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, MessageHandler, Filters,
                          ConversationHandler, CallbackQueryHandler)

import models
from constants import *
from decorator import set_utility_data
from helpers import build_menu, rates_template, bill_template, validate_new_counters_data
from mail import send_mail
from settings import TELEGRAM_TOKEN, RENTER_USERNAME, OWNER_USERNAME

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)

logger = logging.getLogger(__name__)

main_reply_keyboard = [['Счетчики', 'Счет'],
                       ['Шутка', 'Тарифы'],
                       ['Оплачено', 'Пока']]
markup = ReplyKeyboardMarkup(main_reply_keyboard, one_time_keyboard=True)


def start(update, context):
    reply_text = "Привет)"
    update.message.reply_text(reply_text, reply_markup=markup)
    telegram_user = update.effective_user
    user = models.User(telegram_user, chat_id=update.effective_chat.id)

    if not user.exists():
        user.commit()

        if user.username == RENTER_USERNAME:
            models.Counters.load_previous_counters_data(user)
    elif user.chat_id is not update.effective_chat.id:
        user.chat_id = update.effective_chat.id
        user.commit()

    if telegram_user.username == OWNER_USERNAME:
        models.FlatPayment.generate_flat_payments()
    return CHOOSING


def counters_template(counters_last):
    if not counters_last:
        return "Данных нет."

    electricty = f"<b>Электричество:</b> {counters_last.electricity} \n"
    gas = f"<b>Газ:</b> {counters_last.gas} \n"
    water = f"<b>Вода:</b> {counters_last.water} \n"
    date = counters_last.updated or counters_last.created

    return f"<b>На {date.strftime('%d.%m.%Y')}:</b> \n{electricty}{gas}{water}"


def counters(update, context):
    """Return counters btns."""
    counters_last = models.Counters.get_last_user_counters(update.effective_user.id)
    msg = counters_template(counters_last)

    counters_keyboard = [['Новые показания', 'Редактировать'], ['Меню']]
    counters_markup = ReplyKeyboardMarkup(counters_keyboard, one_time_keyboard=False)
    update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=counters_markup)

    return CHOOSING


def new_counters_data(update, context):
    """Set counters data."""
    update.message.reply_text("Электричество:")

    return ELECTRICITY_STATE


def edit_counters_btns(update, context):
    """Return Edit counters buttons."""

    button_list = [
        InlineKeyboardButton("Электроэнергии", callback_data=EDIT_ENERGY),
        InlineKeyboardButton("Воды", callback_data=EDIT_WATER),
        InlineKeyboardButton("Газа", callback_data=EDIT_GAS)
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=2))

    update.message.reply_text('Изменить последние внесенные показания для', reply_markup=reply_markup)
    return EDIT_COUNTERS_DATA


def edit_counters_data_cb(update, context):
    """Handle counters edit btn clicked."""
    query = update.callback_query
    context.user_data['edit_counters'] = query.data
    context.bot.send_message(chat_id=update.effective_chat.id, text='Новое значение:')
    return EDIT_COUNTERS_DATA


def edit_counters_data(update, context):
    """Update data."""
    counter = context.user_data['edit_counters']
    user = update.effective_user
    counters_last, counters_previous = models.Counters.get_last_and_previous_user_counters(user.id)

    if not counters_last:
        update.message.reply_text('Нет предыдущих значений', parse_mode=ParseMode.HTML, reply_markup=markup)
        return CHOOSING
    try:
        new_counter_data = int(update.message.text)
        if counters_last:
            prev_value = getattr(counters_previous, EDIT_COUNTERS_FIELDS[counter])
            validate_new_counters_data(new_counter_data, prev_value)
    except ValueError as e:
        update.message.reply_text('Неправильное значение. Возможно число меньше предыдущих показаний?')
        return EDIT_COUNTERS_DATA

    setattr(counters_last, EDIT_COUNTERS_FIELDS[counter], new_counter_data)
    counters_last.commit()
    msg = counters_template(counters_last)
    update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=markup)
    del context.user_data['edit_counters']
    return CHOOSING


@set_utility_data(ELECTRICITY)
def set_electricity(update, context, state=None, msg=''):
    """Update electricity data and send response."""
    if state == CHOOSING:
        update.message.reply_text(msg, reply_markup=markup)
    update.message.reply_text(msg)
    return state


@set_utility_data(GAS)
def set_gas(update, context, state=None, msg=''):
    """Update gas data and send response."""
    if state == CHOOSING:
        update.message.reply_text(msg, reply_markup=markup)
    update.message.reply_text(msg)
    return state


@set_utility_data(WATER)
def set_water(update, context, state=None, msg=''):
    """Update water data and send response."""
    if state == CHOOSING:
        update.message.reply_text(msg, reply_markup=markup)
    update.message.reply_text(msg)
    return state


@set_utility_data(GAS_COUNTER_PHOTO)
def save_gas_counter_photo(update, context, state=None, msg=''):
    """Save photo."""
    user = update.effective_user

    if state == CHOOSING:
        counters_last = models.Counters.get_last_user_counters(user.id)
        msg = counters_template(counters_last)

        if user.username == RENTER_USERNAME:
            send_mail(user.id, counters_last)
        update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        update.message.reply_text(msg)
    return state


def bill(update, context):
    """Return bill based on latest counters data."""
    msg = bill_template(update.effective_user.id)
    update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=markup)


def joke(update, context):
    """Get joke."""
    response = r.get('https://sv443.net/jokeapi/category/Programming')
    response = response.json()
    if response['type'] == 'single':
        update.message.reply_text(response['joke'], reply_markup=markup)
    else:
        setup = response.get('setup')
        delivery = response.get('delivery')
        update.message.reply_text(f"-{setup}\n-{delivery}", reply_markup=markup)


def prices(update, context):
    """Return current prices for 1 water/electricity/gas."""
    rates = models.Rates.get_default_rates()
    msg = rates_template(rates)
    update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=markup)
    return CHOOSING


def done(update, context):
    update.message.reply_text("Ну, все. Пиши...)")
    return CHOOSING


def main_menu(update, context):
    """Return to main menu."""
    update.message.reply_text('>>', reply_markup=markup)
    return CHOOSING


def other_msgs_handler(update, context):
    """Handle messages that don't have regex handler."""
    update.message.reply_text('Я бы поговорила, но я на работе))', reply_markup=markup)
    return CHOOSING


def generate_paid_months_template():
    """Return beautiful table with paid months."""
    months_paid = models.FlatPayment.get_this_year_payments()
    headers = ['Paid', 'Month', 'Year']
    data = []
    for m in months_paid:
        is_paid = '✓' if m.is_paid else '×'
        month = [is_paid, calendar.month_name[m.month_number], m.year]
        data.append(month)
    return tabulate(data, headers=headers, tablefmt='simple', colalign=("center",))


def get_payments_calendar(update, context):
    """Returns keyboard with 12 month with list of months that were paid.."""
    username = update.effective_user.username
    months_paid_string = generate_paid_months_template()

    if not username == OWNER_USERNAME:
        update.message.reply_text(months_paid_string, parse_mode=ParseMode.HTML, reply_markup=markup)
        return CHOOSING

    months_list = list(filter(None, calendar.month_name))
    months_keyboard = [months_list[i:i + 3] for i in range(0, len(list(months_list)), 3)]
    counters_markup = ReplyKeyboardMarkup(months_keyboard, one_time_keyboard=True)
    update.message.reply_text(months_paid_string, parse_mode=ParseMode.HTML, reply_markup=counters_markup)

    return CALENDAR_STATE


def set_unset_month_paid(update, context):
    """Check is_paid for selected month."""
    if not update.effective_user.username == OWNER_USERNAME:
        update.message.reply_text('Упс, так нельзя.', reply_markup=markup)
        return CHOOSING

    month_name = update.message.text
    if month_name in list(calendar.month_name):
        month_number = list(calendar.month_name).index(month_name)
        models.FlatPayment.mark_as_paid_or_unpaid(month_number)
        months_paid_string = generate_paid_months_template()
        update.message.reply_text(months_paid_string, reply_markup=markup)
    else:
        update.message.reply_text('менюшечка', reply_markup=markup)
    return CHOOSING


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def conversation_handler():
    """Decides how to answer on user messages."""
    default_regex_commands = 'Счетчики|Тарифы|Счет|Шутка|Новые показания|Меню|Пока|payments'
    return ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex('.'), start)
        ],

        states={
            CHOOSING: [MessageHandler(Filters.regex('Счетчики'),
                                      counters),
                       MessageHandler(Filters.regex('Тарифы'),
                                      prices),
                       MessageHandler(Filters.regex('Счет'),
                                      bill),
                       MessageHandler(Filters.regex('Шутка'),
                                      joke),
                       MessageHandler(Filters.regex('Новые показания'),
                                      new_counters_data),
                       MessageHandler(Filters.regex('Редактировать'),
                                      edit_counters_btns),
                       MessageHandler(Filters.regex('Меню'),
                                      main_menu),
                       MessageHandler(Filters.regex('Оплачено'),
                                      get_payments_calendar),
                       MessageHandler(Filters.regex(f'^(?!.*({default_regex_commands}))'),
                                      other_msgs_handler),
                       ],

            ELECTRICITY_STATE: [MessageHandler(Filters.text, set_electricity)],
            GAS_STATE: [MessageHandler(Filters.text, set_gas)],
            GAS_COUNTER_PHOTO_STATE: [MessageHandler(Filters.photo, save_gas_counter_photo)],
            WATER_STATE: [MessageHandler(Filters.text, set_water)],
            CALENDAR_STATE: [MessageHandler(Filters.text, set_unset_month_paid)],
            EDIT_COUNTERS_DATA: [
                MessageHandler(Filters.regex('Меню'),
                               main_menu),
                MessageHandler(Filters.text,
                               edit_counters_data),
                CallbackQueryHandler(edit_counters_data_cb),
            ]
        },

        fallbacks=[MessageHandler(Filters.regex('Пока'), done)],
        name="my_conversation",
        persistent=False
    )


def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = conversation_handler()

    dp.add_handler(conv_handler)
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
