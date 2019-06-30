from functools import wraps

import models
from constants import ELECTRICITY_STATE, GAS_STATE, WATER_STATE, ELECTRICITY, CHOOSING, WATER, GAS


def set_utility_data(option):
    _option = option

    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            """Validates and updates counters data."""
            update, context = args
            new_value = update.message.text
            user_id = update.effective_user.id
            states = [ELECTRICITY_STATE, GAS_STATE, WATER_STATE]
            current_state, msg = get_state(_option)

            try:
                previous_values = models.Counters.get_last_user_counters(user_id)
                validated_value = validate(new_value,   getattr(previous_values, _option, None))
                set_counters_data(validated_value, option, user_id)
            except (TypeError, ValueError) as e:
                if new_value == 'Главное меню':
                    msg = '>>'
                    return function(update, context, CHOOSING, msg)
                msg = 'Неправильное значение, вроде. Попробуй еще.'
                return function(update, context, current_state, msg)

            state = get_next_state(states, current_state)

            return function(update, context, state, msg)
        return wrapper
    return decorator


def get_state(option, current_state=None, msg='Ушло'):
    """Return current state."""
    if option == ELECTRICITY:
        current_state = ELECTRICITY_STATE
        msg = 'Газ:'
    elif option == GAS:
        current_state = GAS_STATE
        msg = 'Вода:'
    elif option == WATER:
        current_state = WATER_STATE

    return current_state, msg


def get_next_state(states, current_state):
    """Return next state."""
    states_index = states.index(current_state)

    if len(states) <= states_index + 1:
        state = CHOOSING
    else:
        state = states[states_index + 1]

    return state


def validate(value, old_value):
    """Validate value."""
    value = int(value)

    if not old_value or (old_value and old_value <= value):
        return value
    else:
        raise ValueError


def set_counters_data(validated_value, option, user_id):
    """Set counters new value."""
    counters = models.Counters.get_current_month_counters_data(user_id)

    if not counters:
        counters = models.Counters()
        counters.user_id = user_id

    setattr(counters, option, validated_value)
    counters.commit()
