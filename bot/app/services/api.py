"""
services/api.py

HTTP-клиент к FAQ Assistant API.

Пермишны проверяются ПЕРЕД каждым защищённым вызовом.
Результат get_permissions() кэшируется на 60 секунд — чтобы не делать
2 HTTP-запроса на каждое действие пользователя.
"""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Кэш пермишнов: {telegram_id: (timestamp, ["perm1", "perm2"])}
# ---------------------------------------------------------------------------
_PERM_CACHE: dict[int, tuple[float, list[str]]] = {}
_PERM_TTL = 60.0  # секунд


def _base() -> str:
    return os.getenv("API_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------

async def sync_user(telegram_id: int, username: str | None, full_name: str | None) -> dict | None:
    """
    POST /api/v1/users/sync
    Возвращает UserResponse с полем status: active | blocked | inactive
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{_base()}/api/v1/users/sync",
                json={"telegram_id": telegram_id, "username": username, "full_name": full_name},
            )
            if r.status_code == 200:
                return r.json()
            logger.warning("sync_user: status=%d body=%s", r.status_code, r.text)
    except httpx.RequestError as e:
        logger.error("sync_user: API unreachable — %s", e)
    return None


async def _get_internal_user_id(telegram_id: int) -> int | None:
    """GET /api/v1/users/by-telegram/{telegram_id}"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{_base()}/api/v1/users/by-telegram/{telegram_id}")
            if r.status_code == 200:
                return r.json()["id"]
            logger.warning("_get_internal_user_id: telegram_id=%d status=%d", telegram_id, r.status_code)
    except httpx.RequestError as e:
        logger.error("_get_internal_user_id: API unreachable — %s", e)
    return None


async def get_permissions(telegram_id: int) -> list[str]:
    """
    GET /api/v1/users/{user_id}/permissions
    Результат кэшируется на _PERM_TTL секунд.
    При любой ошибке возвращает [] (fail-safe).
    """
    now = time.monotonic()
    cached = _PERM_CACHE.get(telegram_id)
    if cached and (now - cached[0]) < _PERM_TTL:
        logger.debug("get_permissions: cache hit for telegram_id=%d", telegram_id)
        return cached[1]

    user_id = await _get_internal_user_id(telegram_id)
    if user_id is None:
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{_base()}/api/v1/users/{user_id}/permissions")
            if r.status_code == 200:
                perms: list[str] = r.json().get("permissions", [])
                _PERM_CACHE[telegram_id] = (now, perms)
                logger.info("get_permissions: telegram_id=%d perms=%s (cached)", telegram_id, perms)
                return perms
            logger.warning("get_permissions: user_id=%d status=%d", user_id, r.status_code)
    except httpx.RequestError as e:
        logger.error("get_permissions: API unreachable — %s", e)
    return []


def invalidate_permissions_cache(telegram_id: int) -> None:
    """Сбросить кэш пермишнов для пользователя (например после смены роли)."""
    _PERM_CACHE.pop(telegram_id, None)


async def has_permission(telegram_id: int, permission_code: str) -> bool:
    """
    Главная проверка доступа. Вызывать ПЕРЕД защищённым эндпоинтом.
    """
    perms = await get_permissions(telegram_id)
    allowed = permission_code in perms
    if not allowed:
        logger.info("has_permission: DENIED telegram_id=%d code=%s", telegram_id, permission_code)
    return allowed


# ---------------------------------------------------------------------------
# Вопросы
# ---------------------------------------------------------------------------

async def ask_question(
    telegram_id: int, question: str, session_id: str | None = None
) -> dict | None:
    """
    POST /api/v1/ask  (x-telegram-id header)
    Ответ: session_id, assistant_message_id, answer, outcome, degradations, chunks
    """
    payload: dict = {"question": question}
    if session_id:
        payload["session_id"] = session_id
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{_base()}/api/v1/ask",
                json=payload,
                headers={"x-telegram-id": str(telegram_id)},
            )
            if r.status_code == 200:
                return r.json()
            logger.warning("ask_question: status=%d body=%s", r.status_code, r.text)
    except httpx.RequestError as e:
        logger.error("ask_question: API unreachable — %s", e)
    return None


# ---------------------------------------------------------------------------
# Обратная связь
# ---------------------------------------------------------------------------

async def rate_message(telegram_id: int, message_id: str, rating: int) -> str:
    """
    POST /api/v1/conversations/messages/{message_id}/feedback
    rating: 1 = 👍, -1 = 👎

    Возвращает строку-статус:
        "ok"        — успешно сохранено
        "not_found" — сообщение не найдено (устарело)
        "error"     — другая ошибка / недоступен
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{_base()}/api/v1/conversations/messages/{message_id}/feedback",
                json={"rating": rating},
                headers={"x-telegram-id": str(telegram_id)},
            )
            if r.status_code == 200:
                return "ok"
            if r.status_code == 404:
                logger.info("rate_message: message_id=%s not found", message_id)
                return "not_found"
            logger.warning("rate_message: status=%d body=%s", r.status_code, r.text)
    except httpx.RequestError as e:
        logger.error("rate_message: API unreachable — %s", e)
    return "error"


# ---------------------------------------------------------------------------
# Документы
# ---------------------------------------------------------------------------

async def upload_document(
    telegram_id: int,
    file_bytes: bytes,
    filename: str,
    title: str,
    required_permission_code: str = "default",
) -> dict | None:
    """
    POST /api/v1/documents  (multipart/form-data, x-telegram-id header)
    """
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{_base()}/api/v1/documents",
                headers={"x-telegram-id": str(telegram_id)},
                data={
                    "title": title,
                    "required_permission_code": required_permission_code,
                },
                files={"file": (filename, file_bytes)},
            )
            if r.status_code == 201:
                return r.json()
            logger.warning("upload_document: status=%d body=%s", r.status_code, r.text)
    except httpx.RequestError as e:
        logger.error("upload_document: API unreachable — %s", e)
    return None
