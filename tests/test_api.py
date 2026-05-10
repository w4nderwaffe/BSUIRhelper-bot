"""
tests/test_api.py

Сценарии:
    1.  has_permission — пермишн есть → True
    2.  has_permission — пермишна нет → False
    3.  has_permission — бэкенд недоступен → False (fail-safe)
    4.  get_permissions — кэш работает (второй вызов не делает HTTP)
    5.  get_permissions — кэш истёк (делает новый запрос)
    6.  invalidate_permissions_cache — сбрасывает кэш
    7.  sync_user — успешная регистрация
    8.  sync_user — бэкенд недоступен → None
    9.  ask_question — успешный ответ
    10. ask_question — бэкенд недоступен → None
    11. rate_message — успех → "ok"
    12. rate_message — 404 → "not_found"
    13. rate_message — ошибка → "error"
    14. upload_document — успех → dict
    15. upload_document — бэкенд недоступен → None
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

import app.services.api as api_module
from app.services.api import (
    has_permission,
    get_permissions,
    invalidate_permissions_cache,
    sync_user,
    ask_question,
    rate_message,
    upload_document,
)

USER_ID = 42
INTERNAL_ID = 7


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    resp.text = str(json_data)
    return resp


# ---------------------------------------------------------------------------
# Вспомогательная функция: мокаем два последовательных GET-запроса
# ---------------------------------------------------------------------------

def _patch_perms(perms: list[str]):
    """Мокает by-telegram + permissions запросы."""
    responses = [
        _mock_response(200, {"id": INTERNAL_ID}),
        _mock_response(200, {"permissions": perms}),
    ]
    client_mock = AsyncMock()
    client_mock.get = AsyncMock(side_effect=responses)
    return client_mock


# ---------------------------------------------------------------------------
# has_permission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_permission_true():
    """Пермишн есть в списке — возвращает True."""
    invalidate_permissions_cache(USER_ID)
    client = _patch_perms(["ask_question", "upload_document"])

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await has_permission(USER_ID, "ask_question")

    assert result is True


@pytest.mark.asyncio
async def test_has_permission_false():
    """Пермишна нет в списке — возвращает False."""
    invalidate_permissions_cache(USER_ID)
    client = _patch_perms(["ask_question"])

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await has_permission(USER_ID, "upload_document")

    assert result is False


@pytest.mark.asyncio
async def test_has_permission_api_unavailable():
    """Бэкенд недоступен — fail-safe возвращает False."""
    invalidate_permissions_cache(USER_ID)

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            side_effect=httpx.RequestError("connection refused")
        )
        result = await has_permission(USER_ID, "ask_question")

    assert result is False


# ---------------------------------------------------------------------------
# Кэш пермишнов
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_permissions_cache_hit():
    """Второй вызов get_permissions берёт данные из кэша без HTTP-запроса."""
    invalidate_permissions_cache(USER_ID)
    client = _patch_perms(["ask_question"])

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await get_permissions(USER_ID)   # первый вызов — HTTP
        call_count_after_first = client.get.call_count

        await get_permissions(USER_ID)   # второй — кэш
        call_count_after_second = client.get.call_count

    assert call_count_after_first == 2        # by-telegram + permissions
    assert call_count_after_second == 2       # второй раз HTTP не вызывался


@pytest.mark.asyncio
async def test_permissions_cache_expired():
    """После истечения TTL делается новый запрос."""
    invalidate_permissions_cache(USER_ID)
    client = _patch_perms(["ask_question"])

    # Подставляем уже просроченную запись в кэш
    api_module._PERM_CACHE[USER_ID] = (time.monotonic() - 999, ["old_perm"])

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        perms = await get_permissions(USER_ID)

    assert perms == ["ask_question"]  # свежие данные, не "old_perm"


@pytest.mark.asyncio
async def test_invalidate_cache():
    """invalidate_permissions_cache сбрасывает кэш для конкретного пользователя."""
    api_module._PERM_CACHE[USER_ID] = (time.monotonic(), ["ask_question"])
    invalidate_permissions_cache(USER_ID)
    assert USER_ID not in api_module._PERM_CACHE


# ---------------------------------------------------------------------------
# sync_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_user_success():
    """Успешная синхронизация — возвращает UserResponse."""
    resp = _mock_response(200, {"id": INTERNAL_ID, "status": "active"})
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(return_value=resp)

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client_mock)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await sync_user(USER_ID, "testuser", "Test User")

    assert result["status"] == "active"
    assert result["id"] == INTERNAL_ID


@pytest.mark.asyncio
async def test_sync_user_unavailable():
    """Бэкенд недоступен — возвращает None без исключения."""
    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            side_effect=httpx.RequestError("timeout")
        )
        result = await sync_user(USER_ID, "testuser", "Test User")

    assert result is None


# ---------------------------------------------------------------------------
# ask_question
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ask_question_success():
    """Успешный запрос к RAG — возвращает ответ."""
    payload = {
        "session_id": "sess-1",
        "assistant_message_id": "msg-1",
        "answer": "Библиотека работает до 20:00",
        "outcome": "success",
        "degradations": [],
        "chunks": [],
    }
    resp = _mock_response(200, payload)
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(return_value=resp)

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client_mock)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await ask_question(USER_ID, "Где библиотека?", session_id="sess-0")

    assert result["answer"] == "Библиотека работает до 20:00"
    assert result["session_id"] == "sess-1"

    # Проверяем что session_id был передан в тело запроса
    call_kwargs = client_mock.post.call_args[1]
    assert call_kwargs["json"]["session_id"] == "sess-0"


@pytest.mark.asyncio
async def test_ask_question_unavailable():
    """Бэкенд недоступен — возвращает None."""
    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            side_effect=httpx.RequestError("timeout")
        )
        result = await ask_question(USER_ID, "Вопрос")

    assert result is None


# ---------------------------------------------------------------------------
# rate_message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_message_ok():
    """200 → "ok"."""
    resp = _mock_response(200, {})
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(return_value=resp)

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client_mock)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await rate_message(USER_ID, "msg-1", 1)

    assert result == "ok"


@pytest.mark.asyncio
async def test_rate_message_not_found():
    """404 → "not_found"."""
    resp = _mock_response(404, {"detail": "not found"})
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(return_value=resp)

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client_mock)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await rate_message(USER_ID, "msg-old", -1)

    assert result == "not_found"


@pytest.mark.asyncio
async def test_rate_message_error():
    """Бэкенд недоступен → "error"."""
    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            side_effect=httpx.RequestError("timeout")
        )
        result = await rate_message(USER_ID, "msg-1", 1)

    assert result == "error"


# ---------------------------------------------------------------------------
# upload_document
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_document_success():
    """201 → возвращает DocumentResponse."""
    resp = _mock_response(201, {"id": "doc-999", "title": "test.pdf"})
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(return_value=resp)

    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client_mock)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await upload_document(USER_ID, b"content", "test.pdf", "test.pdf")

    assert result["id"] == "doc-999"


@pytest.mark.asyncio
async def test_upload_document_unavailable():
    """Бэкенд недоступен → None."""
    with patch("app.services.api.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(
            side_effect=httpx.RequestError("timeout")
        )
        result = await upload_document(USER_ID, b"content", "test.pdf", "test.pdf")

    assert result is None
