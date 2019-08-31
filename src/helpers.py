import requests as r

from mail import send_email
from settings import HEATING_LOGIN, HEATING_PASSWORD, HEATING_LOGIN_API, HEATING_BILL_API, HEATING_PROVIDER_ID


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


def calculate_bill(user_id, rates):
    """Returns fields for a bill."""
    flat_price = rates.get_flat_price()
    exchange_rate = get_exchange_rate()
    bills = rates.calculate_total_price(flat_price, exchange_rate, user_id)

    return flat_price, exchange_rate, bills


def bill_template(user_id, rates):
    """Calculate all data and return template."""
    flat_price, exchange_rate, bills = calculate_bill(user_id, rates)
    communal_services = round(bills['sdpt'] + bills['garbage_removal'], 2)
    total = round(bills['total'])
    water = round(bills['water'], 1)

    if bills['last_counters_created_date']:
        last_counters_date = bills['last_counters_created_date'].strftime('%d.%m.%Y')
    else:
        last_counters_date = bills['last_counters_created_date'] = '--.--.--'

    header = "<i>Счет на основе последних и предпоследних показателей счетчиков.</i>\n"
    date = f"<i>Дата последних показаний {last_counters_date}</i> \n\n"
    flat = f"<b>Квартира:</b> {flat_price} ({exchange_rate})\n"
    services = f"<b>Коммунальные:</b> {communal_services}\n"
    electricity = f"<b>Электричество:</b> {bills['electricity']}\n"
    gas = f"<b>Газ:</b> {bills['gas']} \n"
    water = f"<b>Вода:</b> {water} \n"
    heating = f"<b>Отопление:</b> {bills['heating']} \n"
    total = f"---------------------------\n {total} грн"
    return header + date + flat + services + electricity + gas + water + heating + total


def bill_email_template(user_id, counters_last, rates):
    """Generate bill for sendgrid dynamic template."""
    flat_price, exchange_rate, flat_service_prices = calculate_bill(user_id, rates)
    total, electricity, gas, water = flat_service_prices

    template_data = {
        'electricity_counter': counters_last.electricity,
        'gas_counter': counters_last.gas,
        'gas_counter_photo': counters_last.gas_counter_photo_url,
        'water_counter': counters_last.water,
        'flat_price': flat_price,
        'exchange_rate': exchange_rate,
        'sdpt_garbage': round(rates.sdpt + rates.garbage_removal, 2),
        'electricity': electricity,
        'gas': gas,
        'water': round(water, 1),
        'heating': 'n/a',
        'total': round(total)
    }
    for k, v in template_data.items():
        template_data[k] = str(v)
    return template_data


def validate_new_counters_data(value, old_value):
    """Validate value or raise Value error.."""
    value = int(value)

    if not old_value or (old_value and old_value <= value):
        return value
    else:
        raise ValueError


def get_heating_bill():
    """Login to local heating service. Login and grab bill."""
    try:
        payload = {'email': HEATING_LOGIN, 'password': HEATING_PASSWORD}
        login_response = r.post(HEATING_LOGIN_API, data=payload)

        if login_response.status_code > 200:
            raise r.exceptions.HTTPError
        login_response = login_response.json()
        auth_token = login_response['token']
        account = login_response['account'][0]['Code']
        headers = {'Authorization': auth_token}
        data = {'account': account, 'provider_id': HEATING_PROVIDER_ID}
        bill_response = r.post(HEATING_BILL_API, json=data, headers=headers)

        if bill_response.status_code > 200:
            raise r.exceptions.HTTPError
        bill_response = bill_response.json()
        bill = bill_response['dataset'][0]['sum_topay']
        return bill
    except (IndexError, KeyError, r.ConnectionError, r.HTTPError) as e:
        send_email('Could not get Heating Bill', e)
