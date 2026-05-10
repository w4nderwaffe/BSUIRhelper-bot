# University FAQ Bot

Telegram-бот — интерфейс к RAG-системе университета.

## Структура

```
bot/
├── main.py                  # точка входа
├── requirements.txt
├── .env.example
└── app/
    ├── handlers/
    │   ├── start.py         # /start, приветствие
    │   ├── question.py      # вопросы → RAG → ответ
    │   ├── feedback.py      # inline 👍 / 👎
    │   └── admin.py         # загрузка документов (только ADMIN_ID)
    ├── keyboards/
    │   ├── main.py          # reply-клавиатура главного меню
    │   └── feedback.py      # inline-кнопки оценки
    └── services/
        └── rag.py           # RAG-сервис (сейчас заглушка)
```

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Вставьте BOT_TOKEN и ADMIN_ID в .env

python main.py
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен из BotFather |
| `ADMIN_ID` | Telegram user_id администратора |

## Подключение реального RAG-бэкенда

Замените реализацию в `app/services/rag.py`.  
Сигнатуры функций менять не нужно:

```python
async def ask_question(text: str) -> str: ...
async def add_document(file_bytes: bytes, filename: str) -> bool: ...
```

Пример подключения FastAPI-бэкенда:

```python
import httpx

async def ask_question(text: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post("http://rag-backend/query", json={"question": text})
        return r.json()["answer"]
```
