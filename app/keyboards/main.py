from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_keyboard(can_upload: bool = False, can_manage_users: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="❓ Задать вопрос"), KeyboardButton(text="🔄 Новый разговор")],
    ]

    if can_upload:
        buttons.append([KeyboardButton(text="📂 Загрузить документ")])
        buttons.append([KeyboardButton(text="📋 Документы")])

    if can_manage_users:
        buttons.append([KeyboardButton(text="👥 Пользователи")])
        buttons.append([
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="📣 Рассылка"),
        ])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )
