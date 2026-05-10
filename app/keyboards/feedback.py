from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def feedback_keyboard(assistant_message_id: str) -> InlineKeyboardMarkup:
    """
    Inline-кнопки 👍 / 👎 под ответом RAG.
    assistant_message_id — UUID из ответа /api/v1/ask, нужен для /feedback эндпоинта.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👍 Полезно",
                    callback_data=f"feedback:like:{assistant_message_id}",
                ),
                InlineKeyboardButton(
                    text="👎 Не помогло",
                    callback_data=f"feedback:dislike:{assistant_message_id}",
                ),
            ]
        ]
    )
