"""
conftest.py — общие фикстуры для всех тестов.

Используем pytest-asyncio + unittest.mock.
Реальных HTTP-запросов нет — всё через AsyncMock.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (
    User, Chat, Message, Document,
    CallbackQuery, ReplyKeyboardMarkup,
)

from app.handlers import start, question, admin, feedback


# ---------------------------------------------------------------------------
# Диспетчер и бот
# ---------------------------------------------------------------------------

@pytest.fixture
def bot() -> MagicMock:
    """Мок бота — не делает реальных запросов к Telegram."""
    b = MagicMock(spec=Bot)
    b.id = 123456789
    b.send_chat_action = AsyncMock()
    b.get_file = AsyncMock()
    b.download_file = AsyncMock()
    b.set_my_commands = AsyncMock()
    return b


@pytest.fixture
def storage() -> MemoryStorage:
    return MemoryStorage()


@pytest.fixture
def dp(storage) -> Dispatcher:
    d = Dispatcher(storage=storage)
    d.include_router(start.router)
    d.include_router(admin.router)
    d.include_router(feedback.router)
    d.include_router(question.router)
    return d


# ---------------------------------------------------------------------------
# Telegram-объекты
# ---------------------------------------------------------------------------

def make_user(user_id: int = 111, full_name: str = "Test User", username: str = "testuser") -> User:
    u = MagicMock(spec=User)
    u.id = user_id
    u.full_name = full_name
    u.username = username
    return u


def make_message(
    text: str | None = None,
    user_id: int = 111,
    chat_id: int = 111,
    document: Document | None = None,
    bot: Bot | None = None,
) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = make_user(user_id)
    msg.chat = MagicMock(spec=Chat)
    msg.chat.id = chat_id
    msg.text = text
    msg.document = document
    msg.answer = AsyncMock()
    msg.bot = bot or MagicMock(spec=Bot)
    msg.bot.send_chat_action = AsyncMock()
    msg.bot.get_file = AsyncMock()
    msg.bot.download_file = AsyncMock()
    return msg


def make_document(
    file_name: str = "test.pdf",
    mime_type: str = "application/pdf",
    file_id: str = "file123",
) -> MagicMock:
    doc = MagicMock(spec=Document)
    doc.file_name = file_name
    doc.mime_type = mime_type
    doc.file_id = file_id
    return doc


def make_callback(
    data: str,
    user_id: int = 111,
) -> MagicMock:
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = make_user(user_id)
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    return cb


def make_fsm_context(storage: MemoryStorage, user_id: int = 111) -> FSMContext:
    key = StorageKey(bot_id=0, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)
