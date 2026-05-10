"""
tests/test_feedback.py

Сценарии:
    1. 👍 с пермишном — успешная оценка
    2. 👎 с пермишном — успешная оценка
    3. Оценка без пермишна — отказ, API не вызывается
    4. Оценка устаревшего сообщения (not_found)
    5. Ошибка API при оценке
    6. Кнопки убираются в любом случае (даже при ошибке)
"""

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import make_callback


@pytest.mark.asyncio
async def test_feedback_like_success():
    """👍 с пермишном — оценка сохранена, кнопки убраны."""
    cb = make_callback("feedback:like:msg-abc")

    with patch("app.handlers.feedback.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.feedback.api.rate_message", new=AsyncMock(return_value="ok")):

        from app.handlers.feedback import handle_feedback
        await handle_feedback(cb)

    cb.message.edit_reply_markup.assert_called_once_with(reply_markup=None)
    text = cb.message.answer.call_args[0][0]
    assert "👍" in text or "учтена" in text.lower()


@pytest.mark.asyncio
async def test_feedback_dislike_success():
    """👎 с пермишном — оценка сохранена."""
    cb = make_callback("feedback:dislike:msg-abc")

    with patch("app.handlers.feedback.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.feedback.api.rate_message", new=AsyncMock(return_value="ok")):

        from app.handlers.feedback import handle_feedback
        await handle_feedback(cb)

    text = cb.message.answer.call_args[0][0]
    assert "👎" in text or "учтём" in text.lower()


@pytest.mark.asyncio
async def test_feedback_no_permission():
    """Без пермишна rate_message — отказ, API не вызывается."""
    cb = make_callback("feedback:like:msg-abc")

    with patch("app.handlers.feedback.api.has_permission", new=AsyncMock(return_value=False)), \
         patch("app.handlers.feedback.api.rate_message", new=AsyncMock()) as mock_rate:

        from app.handlers.feedback import handle_feedback
        await handle_feedback(cb)

    mock_rate.assert_not_called()
    cb.answer.assert_called_once()
    assert "⛔" in cb.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_feedback_not_found():
    """Сообщение устарело (not_found) — понятное сообщение пользователю."""
    cb = make_callback("feedback:like:msg-old")

    with patch("app.handlers.feedback.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.feedback.api.rate_message", new=AsyncMock(return_value="not_found")):

        from app.handlers.feedback import handle_feedback
        await handle_feedback(cb)

    text = cb.message.answer.call_args[0][0]
    assert "старое" in text.lower() or "нельзя" in text.lower() or "⏳" in text


@pytest.mark.asyncio
async def test_feedback_api_error():
    """Ошибка API — предупреждение пользователю."""
    cb = make_callback("feedback:like:msg-abc")

    with patch("app.handlers.feedback.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.feedback.api.rate_message", new=AsyncMock(return_value="error")):

        from app.handlers.feedback import handle_feedback
        await handle_feedback(cb)

    text = cb.message.answer.call_args[0][0]
    assert "⚠️" in text or "попробуйте" in text.lower()


@pytest.mark.asyncio
async def test_feedback_buttons_always_removed():
    """Кнопки убираются даже если API вернул ошибку."""
    cb = make_callback("feedback:dislike:msg-abc")

    with patch("app.handlers.feedback.api.has_permission", new=AsyncMock(return_value=True)), \
         patch("app.handlers.feedback.api.rate_message", new=AsyncMock(return_value="error")):

        from app.handlers.feedback import handle_feedback
        await handle_feedback(cb)

    cb.message.edit_reply_markup.assert_called_once_with(reply_markup=None)
