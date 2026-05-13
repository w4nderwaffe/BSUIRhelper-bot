from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.admin import (
    STATUS_ICONS,
    access_keyboard,
    confirm_block_keyboard,
    confirm_delete_keyboard,
    document_actions_keyboard,
    documents_keyboard,
    roles_keyboard,
    users_keyboard,
)
from app.services import api
from app.states.admin import AdminBroadcast, AdminUserSearch

router = Router()
logger = logging.getLogger(__name__)

_PAGE_SIZE = 10
_PAGE_SIZE_USERS = 8


async def _require_upload(telegram_id: int) -> bool:
    return await api.has_permission(telegram_id, "upload_documents")


async def _require_manage_users(telegram_id: int) -> bool:
    return await api.has_permission(telegram_id, "manage_users")


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

async def _build_roles_map() -> dict[int, str]:
    roles = await api.list_roles()
    return {r["id"]: r["name"] for r in roles}


async def _send_user_list(target: Message | CallbackQuery, offset: int = 0) -> None:
    page_data, roles_map = await asyncio.gather(
        api.list_users(offset=offset, limit=_PAGE_SIZE_USERS),
        _build_roles_map(),
    )
    total = page_data["total"]
    page = page_data["items"]

    if not page and total == 0:
        text = "👥 Пользователей пока нет."
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text)
            await target.answer()
        else:
            await target.answer(text)
        return

    kb = users_keyboard(page, roles_map, offset, total)
    text = (
        f"👥 Пользователи ({total})\n"
        f"Стр. {offset // _PAGE_SIZE_USERS + 1}:"
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


async def _show_user_card(target: Message | CallbackQuery, user: dict) -> None:
    roles = await api.list_roles()
    roles_map = {r["id"]: r["name"] for r in roles}
    name = user.get("full_name") or user.get("username") or "—"
    role_name = roles_map.get(user["role_id"], "?")
    text = (
        f"👤 <b>{name}</b>\n"
        f"Telegram ID: <code>{user['telegram_id']}</code>\n"
        f"Роль: <b>{role_name}</b>\n"
        f"Статус: <b>{user.get('status', '—')}</b>\n\n"
        "Выберите новую роль:"
    )
    kb = roles_keyboard(roles, user["id"], user.get("status", "active"))
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.message(F.text == "👥 Пользователи")
async def admin_users_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await _require_manage_users(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await _send_user_list(message, offset=0)


@router.callback_query(F.data.startswith("ul:"))
async def admin_users_page(callback: CallbackQuery) -> None:
    if not await _require_manage_users(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    offset = int(callback.data.split(":", 1)[1])
    await _send_user_list(callback, offset=offset)


@router.callback_query(F.data == "usel:search")
async def admin_users_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _require_manage_users(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminUserSearch.waiting_for_telegram_id)
    await callback.message.edit_text(
        "Перешлите любое сообщение от нужного пользователя\n"
        "или введите его <b>Telegram ID</b> вручную:"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("usel:"))
async def admin_user_select(callback: CallbackQuery) -> None:
    if not await _require_manage_users(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    user_id = int(callback.data.split(":", 1)[1])
    user = await api.get_user_by_id(user_id)
    if user is None:
        await callback.message.edit_text("❌ Пользователь не найден.")
        await callback.answer()
        return
    await _show_user_card(callback, user)


@router.message(AdminUserSearch.waiting_for_telegram_id)
async def admin_users_lookup(message: Message, state: FSMContext) -> None:
    await state.clear()

    if message.forward_from:
        target_tg_id = message.forward_from.id
    elif message.forward_origin:
        await message.answer(
            "⚠️ Пользователь скрыл пересылку сообщений.\n"
            "Попросите его отключить приватность или введите Telegram ID вручную."
        )
        return
    else:
        try:
            target_tg_id = int(message.text.strip())
        except (ValueError, AttributeError):
            await message.answer("❌ Telegram ID должен быть числом.")
            return

    user = await api.get_user_by_telegram_id(target_tg_id)
    if user is None:
        await message.answer("❌ Пользователь не найден.")
        return
    await _show_user_card(message, user)


@router.callback_query(F.data.startswith("ur:"))
async def admin_set_role(callback: CallbackQuery) -> None:
    if not await _require_manage_users(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    _, user_id_str, role_code = callback.data.split(":", 2)
    result = await api.change_user_role(int(user_id_str), role_code)
    if result:
        name = result.get("full_name") or result.get("username") or "пользователя"
        await callback.message.edit_text(f"✅ Роль <b>{name}</b> изменена на <b>{role_code}</b>.")
    else:
        await callback.message.edit_text("❌ Не удалось изменить роль.")
    await callback.answer()


@router.callback_query(F.data.startswith("usask:"))
async def admin_block_ask(callback: CallbackQuery) -> None:
    if not await _require_manage_users(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    user_id = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=confirm_block_keyboard(int(user_id)))
    await callback.answer()


@router.callback_query(F.data.startswith("us:"))
async def admin_set_status(callback: CallbackQuery) -> None:
    if not await _require_manage_users(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    _, user_id_str, new_status = callback.data.split(":", 2)
    result = await api.set_user_status(int(user_id_str), new_status)
    if result:
        name = result.get("full_name") or result.get("username") or "Пользователь"
        icon = "🚫" if new_status == "blocked" else "✅"
        label = "заблокирован" if new_status == "blocked" else "разблокирован"
        await callback.message.edit_text(f"{icon} <b>{name}</b> {label}.")
    else:
        await callback.message.edit_text("❌ Не удалось изменить статус.")
    await callback.answer()


# ---------------------------------------------------------------------------
# Document management
# ---------------------------------------------------------------------------

async def _send_doc_list(telegram_id: int, target: Message | CallbackQuery, offset: int = 0) -> None:
    page_data = await api.list_documents(telegram_id, offset=offset, limit=_PAGE_SIZE)
    total = page_data["total"]
    page = page_data["items"]

    if not page and total == 0:
        text = "📂 Документов пока нет."
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text)
            await target.answer()
        else:
            await target.answer(text)
        return

    kb = documents_keyboard(page, offset, total)
    text = f"📂 Документы ({total} шт.)\nСтр. {offset // _PAGE_SIZE + 1}:"

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.message(F.text == "📋 Документы")
async def admin_docs_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await _require_upload(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await _send_doc_list(message.from_user.id, message, offset=0)


@router.callback_query(F.data.startswith("dl:"))
async def admin_docs_page(callback: CallbackQuery) -> None:
    if not await _require_upload(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    offset = int(callback.data.split(":", 1)[1])
    await _send_doc_list(callback.from_user.id, callback, offset=offset)


@router.callback_query(F.data.startswith("ds:"))
async def admin_doc_select(callback: CallbackQuery) -> None:
    if not await _require_upload(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    doc_id = callback.data.split(":", 1)[1]

    doc = await api.get_document(callback.from_user.id, doc_id)

    if doc:
        status = doc.get("status", "—")
        icon = STATUS_ICONS.get(status, "📄")
        name = doc.get("original_filename") or doc.get("title") or "—"
        perm = doc.get("required_permission_code", "—")
        created = (doc.get("created_at") or "")[:10]
        text = (
            f"{icon} <b>{name}</b>\n"
            f"Статус: <b>{status}</b>\n"
            f"Доступ: <code>{perm}</code>\n"
            f"Загружен: {created}"
        )
        await callback.message.edit_text(text, reply_markup=document_actions_keyboard(doc_id))
    else:
        await callback.message.edit_reply_markup(reply_markup=document_actions_keyboard(doc_id))

    await callback.answer()


@router.callback_query(F.data.startswith("dc:"))
async def admin_doc_delete_ask(callback: CallbackQuery) -> None:
    doc_id = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=confirm_delete_keyboard(doc_id))
    await callback.answer()


@router.callback_query(F.data.startswith("dx:"))
async def admin_doc_delete_confirm(callback: CallbackQuery) -> None:
    if not await _require_upload(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    doc_id = callback.data.split(":", 1)[1]
    ok = await api.delete_document(callback.from_user.id, doc_id)
    if ok:
        await callback.message.edit_text("✅ Документ удалён.")
    else:
        await callback.message.edit_text("❌ Не удалось удалить документ.")
    await callback.answer()


@router.callback_query(F.data.startswith("da:"))
async def admin_doc_access_pick(callback: CallbackQuery) -> None:
    doc_id = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=access_keyboard(doc_id))
    await callback.answer()


@router.callback_query(F.data.startswith("das:"))
async def admin_doc_access_set(callback: CallbackQuery) -> None:
    if not await _require_upload(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    # das:{doc_id}:{permission_code}
    parts = callback.data.split(":", 2)
    doc_id, permission_code = parts[1], parts[2]
    result = await api.update_document_access(callback.from_user.id, doc_id, permission_code)
    if result:
        await callback.message.edit_text(f"✅ Уровень доступа изменён на <b>{permission_code}</b>.")
    else:
        await callback.message.edit_text("❌ Не удалось изменить уровень доступа.")
    await callback.answer()


@router.callback_query(F.data == "adm:cancel")
async def admin_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@router.message(F.text == "📊 Статистика")
async def admin_stats(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await _require_manage_users(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    stats = await api.get_stats()
    if not stats:
        await message.answer("❌ Не удалось получить статистику.")
        return

    total_feedback = stats["feedback_likes"] + stats["feedback_dislikes"]
    like_pct = round(stats["feedback_likes"] / total_feedback * 100) if total_feedback else 0

    await message.answer(
        "<b>📊 Статистика системы</b>\n\n"
        "<b>👥 Пользователи</b>\n"
        f"  Активных: {stats['users_active']}\n"
        f"  Заблокированных: {stats['users_blocked']}\n\n"
        "<b>📂 Документы</b>\n"
        f"  Всего: {stats['documents_total']}\n"
        f"  ✅ Проиндексировано: {stats['documents_ready']}\n"
        f"  ⏳ В обработке: {stats['documents_processing']}\n"
        f"  ❌ С ошибкой: {stats['documents_failed']}\n\n"
        "<b>💬 Диалоги</b>\n"
        f"  Всего сессий: {stats['sessions_total']}\n\n"
        "<b>⭐ Оценки ответов</b>\n"
        f"  👍 {stats['feedback_likes']}   👎 {stats['feedback_dislikes']}"
        + (f"   ({like_pct}% положительных)" if total_feedback else "   (нет оценок)")
    )


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

@router.message(F.text == "📣 Рассылка")
async def admin_broadcast_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await _require_manage_users(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await state.set_state(AdminBroadcast.waiting_for_message)
    await message.answer(
        "📣 Введите текст рассылки.\n"
        "Сообщение будет отправлено всем активным пользователям.\n\n"
        "Для отмены нажмите /start"
    )


@router.message(AdminBroadcast.waiting_for_message, F.text)
async def admin_broadcast_send(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await _require_manage_users(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    users = await api.list_all_users()
    active = [u for u in users if u.get("status") == "active"]

    if not active:
        await message.answer("❌ Нет активных пользователей.")
        return

    status_msg = await message.answer(f"📤 Рассылка {len(active)} пользователям…")
    asyncio.create_task(
        _do_broadcast(message.bot, message.from_user.id, active, message.text, status_msg.message_id)
    )


@router.message(AdminBroadcast.waiting_for_message)
async def admin_broadcast_wrong_input(message: Message) -> None:
    await message.answer(
        "⚠️ Рассылка поддерживает только текст.\n"
        "Введите текст сообщения или нажмите /start для отмены."
    )


async def _do_broadcast(
    bot: Bot,
    sender_id: int,
    users: list[dict],
    text: str,
    status_message_id: int,
) -> None:
    sent = failed = 0
    for user in users:
        tg_id = user.get("telegram_id")
        if not tg_id:
            continue
        try:
            await bot.send_message(tg_id, f"📣 <b>Объявление</b>\n\n{text}")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # ~20 msg/s — в пределах лимита Telegram

    try:
        await bot.edit_message_text(
            f"✅ Рассылка завершена.\nОтправлено: {sent}  |  Ошибок: {failed}",
            chat_id=sender_id,
            message_id=status_message_id,
        )
    except Exception:
        await bot.send_message(
            sender_id,
            f"✅ Рассылка завершена.\nОтправлено: {sent}  |  Ошибок: {failed}",
        )
