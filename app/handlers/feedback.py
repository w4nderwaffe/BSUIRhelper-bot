import logging
from aiogram import Router
from aiogram.types import CallbackQuery

from app.services import api

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data and c.data.startswith("feedback:"))
async def handle_feedback(callback: CallbackQuery) -> None:
    """
    callback_data: feedback:<like|dislike>:<assistant_message_id>
    """
    _, verdict, message_id = callback.data.split(":", 2)
    user = callback.from_user

    # Проверка пермишна перед вызовом API
    if not await api.has_permission(user.id, "ask_question"):
        await callback.answer("⛔ Нет доступа для оценки ответов.", show_alert=True)
        return

    rating = 1 if verdict == "like" else -1

    logger.info(
        "Feedback: telegram_id=%d message_id=%s rating=%d",
        user.id, message_id, rating,
    )

    status = await api.rate_message(
        telegram_id=user.id,
        message_id=message_id,
        rating=rating,
    )

    # Убираем кнопки в любом случае — нельзя оценить дважды
    await callback.message.edit_reply_markup(reply_markup=None)

    if status == "ok":
        text = "👍 Спасибо, ваша оценка учтена!" if verdict == "like" else "👎 Жаль. Учтём для улучшения."
    elif status == "not_found":
        text = "⏳ Это сообщение слишком старое — оценить его уже нельзя."
    else:
        text = "⚠️ Не удалось сохранить оценку, попробуйте позже."

    await callback.answer(text, show_alert=False)
    await callback.message.answer(text)
