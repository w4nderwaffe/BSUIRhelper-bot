import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.services import api
from app.keyboards.feedback import feedback_keyboard

router = Router()
logger = logging.getLogger(__name__)

# Ключ для хранения session_id в FSM-стейте пользователя
SESSION_KEY = "rag_session_id"


@router.message(F.text == "❓ Задать вопрос")
async def btn_ask_question(message: Message) -> None:
    await message.answer("Напишите ваш вопрос, и я найду ответ 🔍")


@router.message(F.text == "🔄 Новый разговор")
async def btn_new_session(message: Message, state: FSMContext) -> None:
    await state.update_data({SESSION_KEY: None})
    await message.answer("🔄 Начат новый разговор — контекст предыдущего очищен.")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_question(message: Message, state: FSMContext) -> None:
    user = message.from_user
    user_text = message.text.strip()

    # --- Проверка пермишна ПЕРЕД вызовом /api/v1/ask ---
    if not await api.has_permission(user.id, "ask_question"):
        await message.answer(
            "⛔ У вас нет доступа к системе вопросов.\n"
            "Обратитесь к администратору."
        )
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    # Достаём session_id из стейта (поддерживает историю диалога)
    data = await state.get_data()
    session_id: str | None = data.get(SESSION_KEY)

    logger.info("Question from telegram_id=%d session=%s: %r", user.id, session_id, user_text)

    result = await api.ask_question(
        telegram_id=user.id,
        question=user_text,
        session_id=session_id,
    )

    if result is None:
        await message.answer(
            "⚠️ Сервис временно недоступен. Попробуйте чуть позже."
        )
        return

    # Сохраняем session_id для следующего сообщения
    await state.update_data({SESSION_KEY: result["session_id"]})

    # assistant_message_id нужен для кнопок фидбека
    msg_id: str = result["assistant_message_id"]

    await message.answer(
        result["answer"],
        reply_markup=feedback_keyboard(msg_id),
    )
