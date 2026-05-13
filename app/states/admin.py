from aiogram.fsm.state import State, StatesGroup


class AdminUserSearch(StatesGroup):
    waiting_for_telegram_id = State()


class AdminBroadcast(StatesGroup):
    waiting_for_message = State()
