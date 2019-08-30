import requests as r

from models import Rates


def build_menu(buttons,
               n_cols,
               header_buttons=None,
               footer_buttons=None):
    """Build buttons for inline buttons."""
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


def rates_template(rates):
    """Generate current rates template."""
    electricity_before = f"<b>Электричество до 100 кВт:</b> {rates.electricity_before_100} грн. \n"
    electricity_after = f"<b>Электричество после 100 кВт:</b> {rates.electricity_after_100} грн. \n"
    gas = f"<b>Газ:</b> {rates.gas} грн. \n"
    water = f"<b>Вода:</b> {rates.water} грн.\n"
    garbage = f"<b>Вывоз мусора:</b> {rates.garbage_removal} грн.\n"
    sdpt = f"<b>СДПТ:</b> {rates.sdpt} грн.\n"

    return f"{electricity_before}{electricity_after}{gas}{water}{garbage}{sdpt}"


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
    rates = Rates.get_default_rates()
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


def validate_new_counters_data(value, old_value):
    """Validate value or raise Value error.."""
    value = int(value)

    if not old_value or (old_value and old_value <= value):
        return value
    else:
        raise ValueError
