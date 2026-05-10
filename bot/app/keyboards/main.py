from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_keyboard(can_upload: bool = False) -> ReplyKeyboardMarkup:
    """
    Клавиатура главного меню.
    Кнопка загрузки показывается только если у пользователя есть пермишн upload_document.
    """
    buttons = [[KeyboardButton(text="❓ Задать вопрос")]]

    if can_upload:
        buttons.append([KeyboardButton(text="📂 Загрузить документ")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )
