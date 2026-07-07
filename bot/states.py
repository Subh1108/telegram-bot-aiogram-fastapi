from aiogram.fsm.state import State, StatesGroup


class SupportForm(StatesGroup):
    waiting_for_message = State()


class BroadcastForm(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()
