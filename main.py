import logging

import requests as r
from telegram import ReplyKeyboardMarkup, ParseMode
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler)

import models
from constants import *
from decorator import set_utility_data
from mail import send_mail
from settings import TELEGRAM_TOKEN, RENTER_USERNAME

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

reply_keyboard = [['Счетчики', 'Счет'],
                  ['Шутка', 'Тарифы'],
                  ['Done']]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)


def start(update, context):
    reply_text = "Здарова."
    update.message.reply_text(reply_text, reply_markup=markup)
    user = models.User(update.effective_user)

    if not user.exists():
        user.commit()

        if user.username == RENTER_USERNAME:
            models.Counters.load_previous_counters_data(user)

    return CHOOSING


def counters_template(counters_last):
    if not counters_last:
        return "Данных нет."

    electricty = f"<b>Электричество:</b> {counters_last.electricity} \n"
    gas = f"<b>Газ:</b> {counters_last.gas} \n"
    water = f"<b>Вода:</b> {counters_last.water} \n"
    date = counters_last.updated or counters_last.created

    return f"<b>На {date.strftime('%d.%m.%Y')}:</b> \n{electricty}{gas}{water}"


def get_exchange_rate():
    """Call privatbank api to get exchange rates for today."""
    response = r.get('https://api.privatbank.ua/p24api/pubinfo?json&exchange&coursid=5')
    exchange_rate_json = response.json()

    for i in exchange_rate_json:
        if i.get('ccy') == 'USD':
            return float(i['sale'])
    raise ValueError


def calculate_bill(user_id):
    """Returns fields for a bill."""
    rates = models.Rates.get_default_rates()
    flat_price = rates.get_flat_price()
    exchange_rate = get_exchange_rate()
    flat_service_prices = rates.calculate_total_price(flat_price, exchange_rate, user_id)

    return rates, flat_price, exchange_rate, flat_service_prices


def bill_template(user_id):
    """Calculate all data and return template."""
    rates, flat_price, exchange_rate, flat_service_prices = calculate_bill(user_id)
    total, electricity, gas, water = flat_service_prices
    communal_services = round(rates.sdpt + rates.garbage_removal, 2)
    total = round(total)
    water = round(water, 1)

    flat = f"<b>Квартира:</b> {flat_price} ({exchange_rate})\n"
    services = f"<b>Коммунальные:</b> {communal_services}\n"
    electricity = f"<b>Электричество:</b> {electricity}\n"
    gas = f"<b>Газ:</b> {gas} \n"
    water = f"<b>Вода:</b> {water} \n"
    heating = f"<b>Отопление: n/a</b> \n"
    total = f"---------------------------\n {total} грн"
    return flat + services + electricity + gas + water + heating + total


def rates_template(rates):
    """Generate current rates template."""
    electricity_before = f"<b>Электричество до 100 кВт:</b> {rates.electricity_before_100} грн. \n"
    electricity_after = f"<b>Электричество после 100 кВт:</b> {rates.electricity_after_100} грн. \n"
    gas = f"<b>Газ:</b> {rates.gas} грн. \n"
    water = f"<b>Вода:</b> {rates.water} грн.\n"
    garbage = f"<b>Вывоз мусора:</b> {rates.garbage_removal} грн.\n"
    sdpt = f"<b>СДПТ:</b> {rates.sdpt} грн.\n"

    return f"{electricity_before}{electricity_after}{gas}{water}{garbage}{sdpt}"


def counters(update, context):
    """Return counters btns."""
    counters_last = models.Counters.get_last_user_counters(update.effective_user.id)
    msg = counters_template(counters_last)

    counters_keyboard = [['Новые показания', 'Меню']]
    counters_markup = ReplyKeyboardMarkup(counters_keyboard, one_time_keyboard=True)
    update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=counters_markup)

    return CHOOSING


def new_counters_data(update, context):
    """Set counters data."""
    update.message.reply_text("Электричество:")

    return ELECTRICITY_STATE


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


def prices(update, context):
    """Return current prices for 1 water/electricity/gas."""
    rates = models.Rates.get_default_rates()
    msg = rates_template(rates)
    update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=markup)
    return CHOOSING


def done(update, context):
    update.message.reply_text("Until next time!")
    return CHOOSING


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


def main_menu(update, context):
    """Return to main menu."""
    update.message.reply_text('>>', reply_markup=markup)
    return CHOOSING


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('start', start)],

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
                       MessageHandler(Filters.regex('Меню'),
                                      main_menu),
                       ],

            ELECTRICITY_STATE: [MessageHandler(Filters.text, set_electricity)],
            GAS_STATE: [MessageHandler(Filters.text, set_gas)],
            WATER_STATE: [MessageHandler(Filters.text, set_water)],
        },

        fallbacks=[MessageHandler(Filters.regex('Done'), done)],
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
