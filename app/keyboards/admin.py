from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

STATUS_ICONS = {
    "uploaded":   "⏳",
    "pending":    "⏳",
    "processing": "🔄",
    "ready":      "✅",
    "failed":     "❌",
    "deleted":    "🗑",
}

_PERMISSION_LABELS = {
    "view_public_docs": "🌐 Публичный",
    "view_student_docs": "🎓 Студенты",
    "view_teacher_docs": "👨‍🏫 Преподаватели",
}


_USER_STATUS_ICONS = {
    "active":   "🟢",
    "blocked":  "🔴",
    "inactive": "⚪",
}

_PAGE_SIZE_USERS = 8


def users_keyboard(
    users: list[dict],
    roles_map: dict[int, str],
    offset: int,
    total: int,
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=(
                f"{_USER_STATUS_ICONS.get(u.get('status', ''), '👤')} "
                f"{(u.get('full_name') or u.get('username') or '—')[:24]} "
                f"· {roles_map.get(u['role_id'], '?')}"
            ),
            callback_data=f"usel:{u['id']}",
        )]
        for u in users
    ]
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"ul:{offset - _PAGE_SIZE_USERS}"))
    if offset + len(users) < total:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"ul:{offset + _PAGE_SIZE_USERS}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="🔍 Найти по ID", callback_data="usel:search")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def roles_keyboard(roles: list[dict], user_id: int, user_status: str = "active") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=r["name"],
            callback_data=f"ur:{user_id}:{r['code']}",
        )]
        for r in roles
    ]
    if user_status == "blocked":
        buttons.append([InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"us:{user_id}:active")])
    else:
        buttons.append([InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"usask:{user_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="adm:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_block_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚫 Да, заблокировать", callback_data=f"us:{user_id}:blocked"),
        InlineKeyboardButton(text="◀ Назад", callback_data="adm:cancel"),
    ]])


def documents_keyboard(docs: list[dict], offset: int, total: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=(
                f"{STATUS_ICONS.get(d.get('status', ''), '📄')} "
                f"{(d.get('original_filename') or d.get('title') or '—')[:30]}"
            ),
            callback_data=f"ds:{d['id']}",
        )]
        for d in docs
    ]
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"dl:{offset - 10}"))
    if offset + len(docs) < total:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"dl:{offset + 10}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def document_actions_keyboard(doc_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"dc:{doc_id}"),
            InlineKeyboardButton(text="🔒 Доступ", callback_data=f"da:{doc_id}"),
        ],
        [InlineKeyboardButton(text="◀ К списку", callback_data="dl:0")],
    ])


def confirm_delete_keyboard(doc_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Удалить", callback_data=f"dx:{doc_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"ds:{doc_id}"),
    ]])


def access_keyboard(doc_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=label,
            callback_data=f"das:{doc_id}:{code}",
        )]
        for code, label in _PERMISSION_LABELS.items()
    ]
    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data=f"ds:{doc_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
