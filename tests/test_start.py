"""
tests/test_start.py

Сценарии:
    1. /start — активный пользователь без пермишна upload
    2. /start — активный пользователь с пермишном upload (администратор)
    3. /start — заблокированный пользователь
    4. /start — неактивный пользователь
    5. /start — бэкенд недоступен (sync_user вернул None)
    6. /help — обычный пользователь
    7. /help — администратор (видит строку про загрузку)
"""

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import make_message


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_active_user():
    """Активный пользователь без upload_documents — приветствие, кнопки без загрузки."""
    msg = make_message(text="/start")

    with patch("app.handlers.start.api.sync_user", new=AsyncMock(return_value={"status": "active"})), \
         patch("app.handlers.start.api.get_permissions", new=AsyncMock(return_value=["ask_question", "rate_message"])):

        from app.handlers.start import cmd_start
        await cmd_start(msg)

    msg.answer.assert_called_once()
    text = msg.answer.call_args[0][0]
    assert "Привет" in text

    # Клавиатура передана, кнопки загрузки нет
    keyboard = msg.answer.call_args[1].get("reply_markup")
    assert keyboard is not None
    button_texts = [btn.text for row in keyboard.keyboard for btn in row]
    assert "❓ Задать вопрос" in button_texts
    assert "📂 Загрузить документ" not in button_texts


@pytest.mark.asyncio
async def test_start_admin_user():
    """Администратор с upload_documents — видит кнопку загрузки."""
    msg = make_message(text="/start")

    with patch("app.handlers.start.api.sync_user", new=AsyncMock(return_value={"status": "active"})), \
         patch("app.handlers.start.api.get_permissions", new=AsyncMock(return_value=["ask_question", "upload_documents", "rate_message"])):

        from app.handlers.start import cmd_start
        await cmd_start(msg)

    keyboard = msg.answer.call_args[1].get("reply_markup")
    button_texts = [btn.text for row in keyboard.keyboard for btn in row]
    assert "📂 Загрузить документ" in button_texts


@pytest.mark.asyncio
async def test_start_blocked_user():
    """Заблокированный пользователь — получает отказ, дальше не идёт."""
    msg = make_message(text="/start")

    with patch("app.handlers.start.api.sync_user", new=AsyncMock(return_value={"status": "blocked"})), \
         patch("app.handlers.start.api.get_permissions", new=AsyncMock()) as mock_perms:

        from app.handlers.start import cmd_start
        await cmd_start(msg)

    text = msg.answer.call_args[0][0]
    assert "заблокирован" in text
    mock_perms.assert_not_called()  # до get_permissions не дошли


@pytest.mark.asyncio
async def test_start_inactive_user():
    """Неактивный пользователь — получает отказ."""
    msg = make_message(text="/start")

    with patch("app.handlers.start.api.sync_user", new=AsyncMock(return_value={"status": "inactive"})):
        from app.handlers.start import cmd_start
        await cmd_start(msg)

    text = msg.answer.call_args[0][0]
    assert "неактивен" in text


@pytest.mark.asyncio
async def test_start_api_unavailable():
    """Бэкенд недоступен (sync_user вернул None) — бот всё равно отвечает."""
    msg = make_message(text="/start")

    with patch("app.handlers.start.api.sync_user", new=AsyncMock(return_value=None)), \
         patch("app.handlers.start.api.get_permissions", new=AsyncMock(return_value=[])):

        from app.handlers.start import cmd_start
        await cmd_start(msg)

    # Бот не упал, ответил приветствием
    msg.answer.assert_called_once()
    assert "Привет" in msg.answer.call_args[0][0]


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_help_regular_user():
    """Обычный пользователь — /help без строки про загрузку документов."""
    msg = make_message(text="/help")

    with patch("app.handlers.start.api.get_permissions", new=AsyncMock(return_value=["ask_question"])):
        from app.handlers.start import cmd_help
        await cmd_help(msg)

    text = msg.answer.call_args[0][0]
    assert "Справка" in text
    assert "Загрузить документ" not in text


@pytest.mark.asyncio
async def test_help_admin_user():
    """Администратор — /help содержит строку про загрузку документов."""
    msg = make_message(text="/help")

    with patch("app.handlers.start.api.get_permissions", new=AsyncMock(return_value=["ask_question", "upload_documents"])):
        from app.handlers.start import cmd_help
        await cmd_help(msg)

    text = msg.answer.call_args[0][0]
    assert "Загрузить документ" in text
