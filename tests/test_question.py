"""
tests/test_question.py

Сценарии:
    1. Кнопка «❓ Задать вопрос» — бот просит написать вопрос
    2. Вопрос с пермишном — успешный ответ от RAG
    3. Вопрос с пермишном — второй вопрос передаёт session_id
    4. Вопрос без пермишна — отказ
    5. Вопрос с пермишном — бэкенд недоступен
"""

import pytest
from unittest.mock import AsyncMock, patch

from aiogram.fsm.storage.memory import MemoryStorage
from tests.conftest import make_message, make_fsm_context


RAG_RESPONSE = {
    "session_id": "sess-abc",
    "assistant_message_id": "msg-xyz",
    "answer": "Расписание доступно на портале.",
    "outcome": "success",
    "degradations": [],
    "chunks": [],
}


@pytest.mark.asyncio
async def test_btn_ask_question():
    """Нажатие кнопки «Задать вопрос» — бот просит написать вопрос."""
    msg = make_message(text="❓ Задать вопрос")

    from app.handlers.question import btn_ask_question
    await btn_ask_question(msg)

    msg.answer.assert_called_once()
    assert "вопрос" in msg.answer.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_question_success():
    """Пользователь с пермишном задаёт вопрос — получает ответ с кнопками."""
    storage = MemoryStorage()
    msg = make_message(text="Когда сессия?")
    state = make_fsm_context(storage, user_id=msg.from_user.id)

    with patch("app.handlers.question.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.question.api.ask_question", new=AsyncMock(return_value=RAG_RESPONSE)):

        from app.handlers.question import handle_question
        await handle_question(msg, state)

    msg.answer.assert_called_once()
    call_kwargs = msg.answer.call_args
    assert "Расписание" in call_kwargs[0][0]
    # Кнопки фидбека присутствуют
    assert call_kwargs[1].get("reply_markup") is not None


@pytest.mark.asyncio
async def test_question_passes_session_id():
    """Второй вопрос передаёт session_id из стейта."""
    storage = MemoryStorage()
    msg = make_message(text="Уточни пожалуйста")
    state = make_fsm_context(storage, user_id=msg.from_user.id)

    # Сохраняем session_id как будто уже был первый вопрос
    await state.update_data({"rag_session_id": "sess-existing"})

    ask_mock = AsyncMock(return_value=RAG_RESPONSE)

    with patch("app.handlers.question.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.question.api.ask_question", new=ask_mock):

        from app.handlers.question import handle_question
        await handle_question(msg, state)

    # Убеждаемся что session_id был передан в API
    _, kwargs = ask_mock.call_args
    assert kwargs.get("session_id") == "sess-existing" or ask_mock.call_args[0][2] == "sess-existing"


@pytest.mark.asyncio
async def test_question_no_permission():
    """Пользователь без пермишна ask_question — получает отказ."""
    storage = MemoryStorage()
    msg = make_message(text="Где деканат?")
    state = make_fsm_context(storage, user_id=msg.from_user.id)

    with patch("app.handlers.question.api.has_permission", new=AsyncMock(return_value=False)), \
         patch("app.handlers.question.api.ask_question", new=AsyncMock()) as mock_ask:

        from app.handlers.question import handle_question
        await handle_question(msg, state)

    text = msg.answer.call_args[0][0]
    assert "нет доступа" in text.lower() or "⛔" in text
    mock_ask.assert_not_called()  # API не вызывался


@pytest.mark.asyncio
async def test_question_api_unavailable():
    """Бэкенд недоступен — вежливое сообщение об ошибке."""
    storage = MemoryStorage()
    msg = make_message(text="Где библиотека?")
    state = make_fsm_context(storage, user_id=msg.from_user.id)

    with patch("app.handlers.question.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.question.api.ask_question", new=AsyncMock(return_value=None)):

        from app.handlers.question import handle_question
        await handle_question(msg, state)

    text = msg.answer.call_args[0][0]
    assert "недоступен" in text.lower() or "⚠️" in text
