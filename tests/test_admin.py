"""
tests/test_admin.py

Сценарии:
    1. Кнопка «Загрузить документ» с пермишном — переходит в состояние ожидания
    2. Кнопка «Загрузить документ» без пермишна — отказ, состояние не меняется
    3. Загрузка PDF — успешно
    4. Загрузка DOCX — успешно
    5. Загрузка TXT — успешно
    6. Загрузка неподдерживаемого формата — отказ, остаётся в состоянии ожидания
    7. Загрузка файла — права отозвали пока ждали (двойная проверка)
    8. Загрузка файла — API вернул ошибку
    9. Текст вместо файла в состоянии ожидания — подсказка
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

from aiogram.fsm.storage.memory import MemoryStorage
from tests.conftest import make_message, make_document, make_fsm_context
from app.states.upload import UploadDocument


def _make_msg_with_doc(mime_type: str = "application/pdf", filename: str = "doc.pdf") -> MagicMock:
    doc = make_document(file_name=filename, mime_type=mime_type)
    msg = make_message()
    msg.document = doc
    file_mock = MagicMock()
    file_mock.file_path = "documents/doc.pdf"
    msg.bot.get_file = AsyncMock(return_value=file_mock)
    msg.bot.download_file = AsyncMock(return_value=BytesIO(b"fake content"))
    return msg


# ---------------------------------------------------------------------------
# Кнопка «Загрузить документ»
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_btn_upload_with_permission():
    """С пермишном — переходит в состояние ожидания файла."""
    storage = MemoryStorage()
    msg = make_message(text="📂 Загрузить документ")
    state = make_fsm_context(storage, user_id=msg.from_user.id)

    with patch("app.handlers.admin.api.has_permission", new=AsyncMock(return_value=True)):
        from app.handlers.admin import btn_upload_documents
        await btn_upload_documents(msg, state)

    msg.answer.assert_called_once()
    assert "Отправьте файл" in msg.answer.call_args[0][0]

    current_state = await state.get_state()
    assert current_state == UploadDocument.waiting_for_file


@pytest.mark.asyncio
async def test_btn_upload_no_permission():
    """Без пермишна — отказ, состояние не меняется."""
    storage = MemoryStorage()
    msg = make_message(text="📂 Загрузить документ")
    state = make_fsm_context(storage, user_id=msg.from_user.id)

    with patch("app.handlers.admin.api.has_permission", new=AsyncMock(return_value=False)):
        from app.handlers.admin import btn_upload_documents
        await btn_upload_documents(msg, state)

    text = msg.answer.call_args[0][0]
    assert "⛔" in text

    current_state = await state.get_state()
    assert current_state is None  # состояние не установлено


# ---------------------------------------------------------------------------
# Загрузка файлов
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("mime_type,filename", [
    ("application/pdf", "lecture.pdf"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "guide.docx"),
    ("text/plain", "faq.txt"),
])
async def test_upload_allowed_formats(mime_type, filename):
    """PDF, DOCX, TXT — все принимаются."""
    storage = MemoryStorage()
    msg = _make_msg_with_doc(mime_type=mime_type, filename=filename)
    state = make_fsm_context(storage, user_id=msg.from_user.id)
    await state.set_state(UploadDocument.waiting_for_file)

    doc_result = {"id": "doc-001", "title": filename}

    with patch("app.handlers.admin.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.admin.api.upload_documents", new=AsyncMock(return_value=doc_result)):

        from app.handlers.admin import handle_document
        await handle_document(msg, state)

    text = msg.answer.call_args[0][0]
    assert "✅" in text
    assert "doc-001" in text

    # Состояние сброшено
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_upload_wrong_format():
    """Неподдерживаемый формат — отказ, остаётся в состоянии ожидания."""
    storage = MemoryStorage()
    msg = _make_msg_with_doc(mime_type="image/jpeg", filename="photo.jpg")
    state = make_fsm_context(storage, user_id=msg.from_user.id)
    await state.set_state(UploadDocument.waiting_for_file)

    with patch("app.handlers.admin.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.admin.api.upload_documents", new=AsyncMock()) as mock_upload:

        from app.handlers.admin import handle_document
        await handle_document(msg, state)

    text = msg.answer.call_args[0][0]
    assert "⚠️" in text
    mock_upload.assert_not_called()

    # Остаётся в состоянии — ждёт правильный файл
    assert await state.get_state() == UploadDocument.waiting_for_file


@pytest.mark.asyncio
async def test_upload_permission_revoked_mid_flow():
    """Права отозвали пока пользователь выбирал файл — двойная проверка."""
    storage = MemoryStorage()
    msg = _make_msg_with_doc()
    state = make_fsm_context(storage, user_id=msg.from_user.id)
    await state.set_state(UploadDocument.waiting_for_file)

    with patch("app.handlers.admin.api.has_permission", new=AsyncMock(return_value=False)), \
         patch("app.handlers.admin.api.upload_documents", new=AsyncMock()) as mock_upload:

        from app.handlers.admin import handle_document
        await handle_document(msg, state)

    text = msg.answer.call_args[0][0]
    assert "⛔" in text
    mock_upload.assert_not_called()
    assert await state.get_state() is None  # состояние сброшено


@pytest.mark.asyncio
async def test_upload_api_error():
    """API вернул None при загрузке — сообщение об ошибке, состояние сброшено."""
    storage = MemoryStorage()
    msg = _make_msg_with_doc()
    state = make_fsm_context(storage, user_id=msg.from_user.id)
    await state.set_state(UploadDocument.waiting_for_file)

    with patch("app.handlers.admin.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.admin.api.upload_documents", new=AsyncMock(return_value=None)):

        from app.handlers.admin import handle_document
        await handle_document(msg, state)

    text = msg.answer.call_args[0][0]
    assert "❌" in text
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_wrong_input_while_waiting():
    """Текст вместо файла в состоянии ожидания — подсказка."""
    msg = make_message(text="а можно просто ссылку?")

    from app.handlers.admin import handle_wrong_input_while_waiting
    await handle_wrong_input_while_waiting(msg)

    text = msg.answer.call_args[0][0]
    assert "файл" in text.lower() or "📎" in text
