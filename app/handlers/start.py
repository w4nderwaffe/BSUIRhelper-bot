import logging
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.services import api
from app.keyboards.main import main_keyboard

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user

    # Регистрируем / обновляем пользователя и сразу читаем его статус
    user_data = await api.sync_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )

    # Проверяем статус — blocked / inactive не пускаем дальше
    if user_data is not None:
        status = user_data.get("status", "active")
        if status == "blocked":
            await message.answer(
                "⛔ Ваш аккаунт заблокирован.\n"
                "Обратитесь к администратору системы."
            )
            logger.warning("Blocked user tried to start: telegram_id=%d", user.id)
            return
        if status == "inactive":
            await message.answer(
                "⏸ Ваш аккаунт неактивен.\n"
                "Обратитесь к администратору системы."
            )
            logger.warning("Inactive user tried to start: telegram_id=%d", user.id)
            return

    # Получаем пермишны чтобы показать правильную клавиатуру
    perms = await api.get_permissions(user.id)
    can_upload = "upload_documents" in perms
    can_manage_users = "manage_users" in perms

    logger.info("User started: telegram_id=%d can_upload=%s can_manage_users=%s", user.id, can_upload, can_manage_users)

    await message.answer(
        f"👋 Привет, <b>{user.full_name}</b>!\n\n"
        "Я FAQ-бот университета. Задайте вопрос — я найду ответ в базе знаний.\n\n"
        "Используйте кнопку ниже или просто напишите вопрос.",
        reply_markup=main_keyboard(can_upload=can_upload, can_manage_users=can_manage_users),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    user = message.from_user
    perms = await api.get_permissions(user.id)
    can_upload = "upload_documents" in perms
    can_manage_users = "manage_users" in perms

    lines = [
        "📖 <b>Справка по боту</b>\n",
        "Я FAQ-ассистент университета. Задайте вопрос обычным сообщением — "
        "я найду ответ в базе знаний.\n",
        "<b>Доступные команды:</b>",
        "/start — главное меню",
        "/help — эта справка\n",
        "<b>Кнопки:</b>",
        "❓ Задать вопрос — начать диалог с ассистентом",
    ]

    if can_upload:
        lines.append("📂 Загрузить документ — добавить PDF, DOCX, TXT, HTML или MD в базу знаний")
        lines.append("📋 Документы — управление документами в базе знаний")

    if can_manage_users:
        lines.append("👥 Пользователи — управление ролями пользователей")

    lines.append("\nПосле каждого ответа можно нажать 👍 или 👎 — это помогает улучшать систему.")

    await message.answer("\n".join(lines))
