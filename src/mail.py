from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from src.settings import FROM_EMAIL, TO_EMAIL, SENDGRID_API_KEY, SENDGRID_TEMPLATE_ID


def send_mail(user_id, counters_last):
    """Send email via Sendgrid."""
    from src.main import calculate_bill
    rates, flat_price, exchange_rate, flat_service_prices = calculate_bill(user_id)
    total, electricity, gas, water = flat_service_prices

    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=TO_EMAIL,
        subject='Новые данные по коммунальным услугам',
        html_content='Дадада'
    )

    template_data = {
        'electricity_counter': counters_last.electricity,
        'gas_counter': counters_last.gas,
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

    message.dynamic_template_data = template_data
    message.template_id = SENDGRID_TEMPLATE_ID
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        print(str(e))
