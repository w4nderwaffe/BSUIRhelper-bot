from aiogram.fsm.state import State, StatesGroup


class UploadDocument(StatesGroup):
    waiting_for_file = State()  # бот ждёт файл или URL после нажатия кнопки
