import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.services import api
from app.states.upload import UploadDocument

router = Router()
logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


@router.message(F.text == "📂 Загрузить документ")
async def btn_upload_document(message: Message, state: FSMContext) -> None:
    user = message.from_user

    # Проверка пермишна ДО того как принимать файл
    if not await api.has_permission(user.id, "upload_document"):
        await message.answer(
            "⛔ У вас нет прав для загрузки документов.\n"
            "Обратитесь к администратору системы."
        )
        return

    # Переводим пользователя в состояние ожидания файла
    await state.set_state(UploadDocument.waiting_for_file)
    await message.answer(
        "📎 Отправьте файл (PDF, DOCX, TXT) — я добавлю его в базу знаний.\n\n"
        "Для отмены нажмите /start"
    )


@router.message(UploadDocument.waiting_for_file, F.document)
async def handle_document(message: Message, state: FSMContext) -> None:
    user = message.from_user
    doc = message.document

    # Двойная проверка пермишна — на случай если права сменились пока ждали файл
    if not await api.has_permission(user.id, "upload_document"):
        await state.clear()
        await message.answer(
            "⛔ У вас нет прав для загрузки документов.\n"
            "Обратитесь к администратору системы."
        )
        return

    if doc.mime_type not in ALLOWED_MIME_TYPES:
        await message.answer(
            "⚠️ Поддерживаются форматы: PDF, DOCX, TXT.\n"
            "Отправьте файл нужного формата или нажмите /start для отмены."
        )
        return  # остаёмся в состоянии — ждём правильный файл

    await message.answer(f"⏳ Загружаю <b>{doc.file_name}</b>…")

    file = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    content = file_bytes.read()

    result = await api.upload_document(
        telegram_id=user.id,
        file_bytes=content,
        filename=doc.file_name,
        title=doc.file_name,
        required_permission_code="default",
    )

    # Выходим из состояния в любом случае
    await state.clear()

    if result:
        logger.info(
            "Document uploaded: telegram_id=%d file=%s doc_id=%s",
            user.id, doc.file_name, result.get("id"),
        )
        await message.answer(
            f"✅ Документ <b>{doc.file_name}</b> успешно добавлен в базу знаний.\n"
            f"ID: <code>{result['id']}</code>"
        )
    else:
        await message.answer("❌ Не удалось загрузить документ. Попробуйте позже.")


@router.message(UploadDocument.waiting_for_file)
async def handle_wrong_input_while_waiting(message: Message) -> None:
    """Пользователь написал текст вместо того чтобы отправить файл."""
    await message.answer(
        "📎 Пожалуйста, отправьте файл (PDF, DOCX, TXT).\n"
        "Для отмены нажмите /start"
    )
