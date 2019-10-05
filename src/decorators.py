from functools import wraps

from telegram import ChatAction

import models
from constants import ELECTRICITY_STATE, GAS_STATE, WATER_STATE, ELECTRICITY, CHOOSING, WATER, GAS, \
    GAS_COUNTER_PHOTO_STATE, GAS_COUNTER_PHOTO
from helpers import validate_new_counters_data

states = [ELECTRICITY_STATE, WATER_STATE, GAS_STATE, GAS_COUNTER_PHOTO_STATE]


def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        return func(update, context, *args, **kwargs)

    return command_func


def set_utility_data(option):
    _option = option

    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            """Validates and updates counters data."""
            update, context = args
            new_value = update.message.text
            user_id = update.effective_user.id
            current_state, msg = get_state(_option)
            return process_counters_data(*args, _option, new_value, user_id, function, current_state, msg)
        return wrapper
    return decorator


def get_state(option, current_state=None, next_msg='Отлично. Теперь можно получить счет :)'):
    """Return current state."""
    if option == ELECTRICITY:
        current_state = ELECTRICITY_STATE
        next_msg = 'Вода:'
    elif option == GAS:
        current_state = GAS_STATE
        next_msg = 'фото газового счетчика :)'
    elif option == WATER:
        current_state = WATER_STATE
        next_msg = 'Газ:'
    elif option == GAS_COUNTER_PHOTO:
        current_state = GAS_COUNTER_PHOTO_STATE

    return current_state, next_msg


def process_counters_data(*args):
    """Handle new counters data."""
    update, context, _option, new_value, user_id, function, current_state, msg = args

    try:
        if current_state is not GAS_COUNTER_PHOTO_STATE:
            previous_counter_data = models.Counters.get_last_user_counters(user_id)
            previous_value = getattr(previous_counter_data, _option, None)
            validated_value = validate_new_counters_data(new_value, previous_value)
        else:
            received_photo = update.message.photo[-1]
            img = received_photo.get_file()
            validated_value = img.file_path
        set_counters_data(validated_value, _option, user_id)
    except (TypeError, ValueError) as e:
        if new_value == 'Меню':
            msg = '>>'
            return function(update, context, CHOOSING, msg)
        msg = 'Ошибка. Возможно значение меньше предыдущего.'
        return function(update, context, current_state, msg)
    else:
        state = get_next_state(current_state)
        return function(update, context, state, msg)


def get_next_state(current_state):
    """Return next state."""
    states_index = states.index(current_state)

    if len(states) <= states_index + 1:
        state = CHOOSING
    else:
        state = states[states_index + 1]

    return state


def set_counters_data(validated_value, option, user_id):
    """Set counters new value."""
    counters = models.Counters.get_current_month_counters_data(user_id)

    if not counters:
        counters = models.Counters()
        counters.user_id = user_id

    setattr(counters, option, validated_value)
    counters.commit()
