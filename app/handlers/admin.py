import asyncio
import logging
from aiogram import Bot, Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.services import api
from app.states.upload import UploadDocument

_POLL_INTERVAL = 15   # секунд между проверками
_POLL_TIMEOUT  = 600  # максимум 10 минут

router = Router()
logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/html",
    "application/xhtml+xml",
    "text/markdown",
    "text/x-markdown",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html", ".htm", ".md", ".markdown"}


async def _poll_indexing(bot: Bot, telegram_id: int, doc_id: str, filename: str) -> None:
    attempts = _POLL_TIMEOUT // _POLL_INTERVAL
    for _ in range(attempts):
        await asyncio.sleep(_POLL_INTERVAL)
        status = await api.get_document_status(telegram_id, doc_id)
        if status == "ready":
            await bot.send_message(
                telegram_id,
                f"✅ <b>{filename}</b> проиндексирован и доступен для поиска!",
            )
            return
        if status == "failed":
            await bot.send_message(
                telegram_id,
                f"❌ Ошибка индексации <b>{filename}</b>. Попробуйте загрузить заново.",
            )
            return
        if status is None:
            return  # документ удалён или недоступен
    await bot.send_message(
        telegram_id,
        f"⚠️ Индексация <b>{filename}</b> занимает дольше обычного.\n"
        "Проверьте статус в разделе 📋 Документы.",
    )


@router.message(F.text == "📂 Загрузить документ")
async def btn_upload_documents(message: Message, state: FSMContext) -> None:
    user = message.from_user

    # Проверка пермишна ДО того как принимать файл
    if not await api.has_permission(user.id, "upload_documents"):
        await message.answer(
            "⛔ У вас нет прав для загрузки документов.\n"
            "Обратитесь к администратору системы."
        )
        return

    # Переводим пользователя в состояние ожидания файла
    await state.set_state(UploadDocument.waiting_for_file)
    await message.answer(
        "📎 Отправьте файл (PDF, DOCX, TXT, HTML, MD) — я добавлю его в базу знаний.\n\n"
        "Для отмены нажмите /start"
    )


@router.message(UploadDocument.waiting_for_file, F.document)
async def handle_document(message: Message, state: FSMContext) -> None:
    user = message.from_user
    doc = message.document

    # Двойная проверка пермишна — на случай если права сменились пока ждали файл
    if not await api.has_permission(user.id, "upload_documents"):
        await state.clear()
        await message.answer(
            "⛔ У вас нет прав для загрузки документов.\n"
            "Обратитесь к администратору системы."
        )
        return

    filename_lower = (doc.file_name or "").lower()
    ext = "." + filename_lower.rsplit(".", 1)[-1] if "." in filename_lower else ""
    mime_ok = doc.mime_type in ALLOWED_MIME_TYPES
    ext_ok = ext in ALLOWED_EXTENSIONS
    if not mime_ok and not ext_ok:
        await message.answer(
            "⚠️ Поддерживаются форматы: PDF, DOCX, TXT, HTML, MD.\n"
            "Отправьте файл нужного формата или нажмите /start для отмены."
        )
        return  # остаёмся в состоянии — ждём правильный файл

    await message.answer(f"⏳ Загружаю <b>{doc.file_name}</b>…")

    file = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    content = file_bytes.read()

    result = await api.upload_documents(
        telegram_id=user.id,
        file_bytes=content,
        filename=doc.file_name,
        title=doc.file_name,
        required_permission_code="view_public_docs",
    )

    if result:
        doc_id = result.get("id")
        logger.info(
            "Document uploaded: telegram_id=%d file=%s doc_id=%s",
            user.id, doc.file_name, doc_id,
        )
        await message.answer(
            f"✅ <b>{doc.file_name}</b> загружен, начинается индексация…\n"
            f"<code>{doc_id}</code>\n\n"
            "Отправьте ещё файл или нажмите /start для выхода.\n"
            "Уведомлю когда документ будет готов к поиску 🔔"
        )
        asyncio.create_task(
            _poll_indexing(message.bot, user.id, doc_id, doc.file_name)
        )
    else:
        await message.answer(
            f"❌ Не удалось загрузить <b>{doc.file_name}</b>. Попробуйте ещё раз или нажмите /start."
        )


@router.message(UploadDocument.waiting_for_file)
async def handle_wrong_input_while_waiting(message: Message) -> None:
    await message.answer(
        "📎 Пожалуйста, отправьте файл (PDF, DOCX, TXT, HTML, MD).\n"
        "Для отмены нажмите /start"
    )
