# main.py - CONTENTGPT bot (production, aiogram v3)
# Features:
# - Generation: post/caption/story/ideas + "my style" analysis + edit/regenerate + save
# - Payments: YooKassa via yandex_kassa_handler.py (poll status) + Telegram Stars
# - Settings: notifications toggles, export CSV, saved content
# - Admin: basic stats
#
# Требования (env):
# TELEGRAM_BOT_TOKEN, ADMIN_ID (желательно),
# YANDEX_GPT_API_KEY, YANDEX_GPT_FOLDER_ID (для генерации),
# YANDEX_KASSA_SHOP_ID, YANDEX_KASSA_SECRET_KEY (для YooKassa),
# DATABASE_PATH (опционально), REQUEST_TIMEOUT (опционально)

import asyncio
import csv
import io
import json
import os
import sqlite3
import uuid
import time
from sqlite3 import OperationalError, connect
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import requests
from loguru import logger

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery,
)
from aiogram.types.input_file import BufferedInputFile

from config import settings, SUBSCRIPTION_PLANS, CONTENT_TYPES
from yandex_kassa_handler import kassa


# ----------------- LOGGING -----------------
logger.add("bot.log", rotation="100 MB", retention="10 days")


# ----------------- BOT -----------------
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# ----------------- DB -----------------
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")

def get_db_connection():
    """Connection pool с улучшениями для конкурентности"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # ← Ускорение, но безопасно
    return conn


def init_database() -> None:
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        subscription_type TEXT DEFAULT 'free',
        subscription_until TEXT,
        bonus_points INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS generation_counter (
        user_id INTEGER,
        date TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY(user_id, date),
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        notif_features INTEGER DEFAULT 1,
        notif_promos INTEGER DEFAULT 1,
        notif_reminders INTEGER DEFAULT 1,
        user_style TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        provider TEXT,
        external_id TEXT,
        order_id TEXT,
        subscription_type TEXT,
        amount REAL,
        currency TEXT,
        status TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS generation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content_type TEXT,
        prompt TEXT,
        content TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE SET NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS saved_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content_type TEXT,
        prompt TEXT,
        content TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()
    logger.info("✅ DB initialized at {}", DATABASE_PATH)


def get_or_create_user(user_id: int, username: str = "", first_name: str = ""):
    """Гарантировать создание юзера перед использованием"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name, subscription_type)
                VALUES (?, ?, ?, 'free')
            """, (user_id, username, first_name))
            
            cursor.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
            logger.info(f"✅ Создан юзер {user_id}")
        
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        logger.warning(f"⚠️ Юзер {user_id} уже существует")
    except sqlite3.OperationalError as e:
        logger.error(f"❌ Ошибка БД при создании юзера {user_id}: {e}")

def increment_generation_counter(user_id: int):
    """Инкремент счётчика с проверкой"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверка существования
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            logger.error(f"❌ Юзер {user_id} не существует! Создаю...")
            conn.close()
            get_or_create_user(user_id)
            conn = get_db_connection()
            cursor = conn.cursor()
        
        # Инкремент
        cursor.execute("""
            INSERT OR REPLACE INTO generation_counter (user_id, date, count)
            VALUES (?, ?, COALESCE((
                SELECT count FROM generation_counter 
                WHERE user_id = ? AND date = ?
            ), 0) + 1)
        """, (user_id, today, user_id, today))
        
        conn.commit()
        conn.close()
        logger.debug(f"✅ Счётчик +1 для {user_id}")
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            logger.error(f"⚠️ БД заблокирована: {e}")
        else:
            logger.error(f"❌ БД ошибка: {e}")


def is_user_admin(user_id: int) -> bool:
    admin_id = getattr(settings, "ADMIN_ID", None)
    if admin_id and str(user_id) == str(admin_id):
        return True

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0])


def get_user_info(user_id: int) -> Optional[Dict[str, Any]]:
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, username, first_name, subscription_type, subscription_until, bonus_points, is_admin
        FROM users WHERE user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None
    return {
        "user_id": row[0],
        "username": row[1] or "не указан",
        "first_name": row[2] or "Пользователь",
        "subscription_type": row[3] or "free",
        "subscription_until": row[4],
        "bonus_points": int(row[5] or 0),
        "is_admin": int(row[6] or 0),
    }


def _plan_daily_limit(plan: Dict[str, Any]) -> int:
    # совместимость: daily_limit (новое) / monthly_limit (старое имя в некоторых версиях)
    if "daily_limit" in plan and isinstance(plan["daily_limit"], int):
        return plan["daily_limit"]
    if "monthly_limit" in plan and isinstance(plan["monthly_limit"], int):
        return plan["monthly_limit"]
    return 5


def check_generation_limit(user_id: int) -> Tuple[bool, int, int]:
    if is_user_admin(user_id):
        return True, 0, 999999

    user = get_user_info(user_id)
    sub_type = (user or {}).get("subscription_type", "free")
    plan = SUBSCRIPTION_PLANS.get(sub_type, SUBSCRIPTION_PLANS.get("free", {"daily_limit": 5}))
    limit = _plan_daily_limit(plan)

    today = datetime.now().strftime("%Y-%m-%d")

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT count FROM generation_counter WHERE user_id = ? AND date = ?", (user_id, today))
    row = cur.fetchone()
    conn.close()

    used = int(row[0]) if row else 0
    return used < limit, used, limit


def increment_generation_counter(user_id: int) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO generation_counter (user_id, date, count)
    VALUES (?, ?, 1)
    ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1
    """, (user_id, today))

    conn.commit()
    conn.close()


def save_generation(user_id: int, content_type: str, prompt: str, content: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO generation_history (user_id, content_type, prompt, content)
    VALUES (?, ?, ?, ?)
    """, (user_id, content_type, prompt, content))
    conn.commit()
    conn.close()


def save_content(user_id: int, content_type: str, prompt: str, content: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO saved_content (user_id, content_type, prompt, content)
    VALUES (?, ?, ?, ?)
    """, (user_id, content_type, prompt, content))
    conn.commit()
    conn.close()


def get_saved_last(user_id: int, limit: int = 10):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, content_type, content, created_at
    FROM saved_content
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT ?
    """, (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_style(user_id: int) -> Optional[str]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_style FROM user_settings WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def save_user_style(user_id: int, style: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE user_settings SET user_style = ? WHERE user_id = ?", (style, user_id))
    conn.commit()
    conn.close()


def toggle_notification(user_id: int, field: str) -> bool:
    # field: notif_features / notif_promos / notif_reminders
    if field not in ("notif_features", "notif_promos", "notif_reminders"):
        return False

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT {field} FROM user_settings WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    current = int(row[0]) if row else 1
    new_value = 0 if current else 1

    cur.execute(f"UPDATE user_settings SET {field} = ? WHERE user_id = ?", (new_value, user_id))
    conn.commit()
    conn.close()
    return bool(new_value)


def get_notifications(user_id: int) -> Tuple[int, int, int]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT notif_features, notif_promos, notif_reminders
    FROM user_settings WHERE user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return 1, 1, 1
    return int(row[0]), int(row[1]), int(row[2])


def update_subscription(user_id: int, sub_type: str, days: int = 30) -> None:
    until = datetime.now() + timedelta(days=days)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE users
    SET subscription_type = ?, subscription_until = ?, updated_at = datetime('now')
    WHERE user_id = ?
    """, (sub_type, until.isoformat(), user_id))
    conn.commit()
    conn.close()


def admin_stats() -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = int(cur.fetchone()[0])

    cur.execute("SELECT COUNT(*) FROM users WHERE subscription_type != 'free'")
    paid_users = int(cur.fetchone()[0])

    cur.execute("SELECT COUNT(*) FROM generation_history")
    gens = int(cur.fetchone()[0])

    cur.execute("SELECT COUNT(*) FROM payments WHERE status = 'completed'")
    completed_payments = int(cur.fetchone()[0])

    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
    revenue = float(cur.fetchone()[0] or 0)

    conn.close()
    return {
        "total_users": total_users,
        "paid_users": paid_users,
        "generations": gens,
        "completed_payments": completed_payments,
        "revenue": revenue,
    }


# ----------------- GPT (sync -> async wrapper) -----------------
class YandexGPTHandler:
    API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    def __init__(self):
        self.api_key = getattr(settings, "YANDEX_GPT_API_KEY", None)
        self.folder_id = getattr(settings, "YANDEX_GPT_FOLDER_ID", None)

    def _sync_generate(self, prompt: str, content_type: str) -> Optional[str]:
        if not self.api_key or not self.folder_id:
            logger.warning("⚠️ YandexGPT not configured")
            return None

        system_prompts = {
            "post": "Ты профессиональный копирайтер для соцсетей. Дай структурированный пост с эмодзи и мягким CTA.",
            "caption": "Ты эксперт по подписям. Дай 2 версии (формальная/неформальная) + хештеги.",
            "story": "Ты сторителлер. Сгенерируй сценарий сторис в 5-7 пунктов + вопросы для вовлечения.",
            "ideas": "Ты генератор идей. Дай 10 идей контента, разнообразных по формату.",
            "style_analysis": "Ты анализируешь стиль автора. Коротко опиши стиль (3-5 предложений) и ключевые приемы.",
        }
        system_prompt = system_prompts.get(content_type, system_prompts["post"])

        payload = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt/latest",
            "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": "1500"},
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": prompt},
            ],
        }

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        timeout = getattr(settings, "REQUEST_TIMEOUT", 30)

        r = requests.post(self.API_URL, json=payload, headers=headers, timeout=timeout)
        if r.status_code != 200:
            logger.error("❌ YandexGPT error {} {}", r.status_code, r.text[:200])
            return None

        data = r.json()
        try:
            return data["result"]["alternatives"][0]["message"]["text"]
        except Exception:
            logger.error("❌ Unexpected YandexGPT response shape")
            return None

    async def generate(self, prompt: str, content_type: str) -> Optional[str]:
        return await asyncio.to_thread(self._sync_generate, prompt, content_type)


gpt = YandexGPTHandler()


# ----------------- UI helpers -----------------
def bottom_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📝 Генерация"), KeyboardButton(text="💎 Подписки")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="💬 Обратная связь")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="👨‍💼 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def generation_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Пост", callback_data="gen:post")],
        [InlineKeyboardButton(text="💬 Подпись", callback_data="gen:caption")],
        [InlineKeyboardButton(text="📱 История", callback_data="gen:story")],
        [InlineKeyboardButton(text="💡 Идеи", callback_data="gen:ideas")],
        [InlineKeyboardButton(text="🤖 Мой стиль", callback_data="gen:style")],
    ])


def after_generation_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="content:save")],
        [InlineKeyboardButton(text="✏️ Правки", callback_data="content:edit")],
        [InlineKeyboardButton(text="🔄 Ещё вариант", callback_data="content:regen")],
        [InlineKeyboardButton(text="⬅️ В меню генерации", callback_data="nav:genmenu")],
    ])


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings:notif")],
        [InlineKeyboardButton(text="📥 Экспорт", callback_data="settings:export")],
        [InlineKeyboardButton(text="📚 Сохранённое", callback_data="settings:saved")],
    ])


def notif_kb(user_id: int) -> InlineKeyboardMarkup:
    f1, f2, f3 = get_notifications(user_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'✅' if f1 else '❌'} Новые функции", callback_data="settings:toggle:notif_features")],
        [InlineKeyboardButton(text=f"{'✅' if f2 else '❌'} Акции", callback_data="settings:toggle:notif_promos")],
        [InlineKeyboardButton(text=f"{'✅' if f3 else '❌'} Напоминания", callback_data="settings:toggle:notif_reminders")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:settings")],
    ])


# ----------------- FSM -----------------
class GenStates(StatesGroup):
    post_topic = State()
    post_style = State()
    post_audience = State()
    post_cta = State()

    caption_photo = State()
    caption_task = State()

    story_vector = State()
    ideas_theme = State()

    style_examples = State()


class EditStates(StatesGroup):
    waiting_edit = State()


# ----------------- In-memory last content cache -----------------
last_content: Dict[int, Dict[str, str]] = {}  # user_id -> {content_type, prompt, content}


# ----------------- Start / basic -----------------
@router.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Пользователь"

    get_or_create_user(uid, username, first_name)

    is_admin = is_user_admin(uid)
    has_limit, used, limit = check_generation_limit(uid)

    limit_text = "Безлимит (админ)" if is_admin else f"{used}/{limit} (сегодня)"
    text = (
        f"🚀 CONTENTGPT BOT\n\n"
        f"Привет, {first_name}!\n"
        f"Лимит генерации: {limit_text}\n\n"
        f"Выбирай раздел кнопками ниже."
    )
    await message.answer(text, reply_markup=bottom_keyboard(is_admin))


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ Помощь\n\n"
        "📝 Генерация: пост / подпись / сторис / идеи / мой стиль\n"
        "💎 Подписки: YooKassa (карта) или Telegram Stars\n"
        "⚙️ Настройки: уведомления, экспорт, сохранённое\n"
    )


# ----------------- Main menu buttons -----------------
@router.message(F.text == "📝 Генерация")
async def btn_generation(message: Message):
    uid = message.from_user.id
    has_limit, used, limit = check_generation_limit(uid)
    if not has_limit:
        await message.answer(f"❌ Лимит исчерпан ({used}/{limit}).\nОформи подписку в разделе 💎 Подписки.")
        return
    await message.answer("📝 Выбери тип генерации:", reply_markup=generation_menu_kb())


@router.message(F.text == "👤 Профиль")
async def btn_profile(message: Message):
    uid = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Пользователь"
    
    # ✅ Создаём профиль если его нет
    get_or_create_user(uid, username, first_name)
    
    user = get_user_info(uid)
    if not user:
        await message.answer("❌ Профиль не найден.")
        return

    plan = SUBSCRIPTION_PLANS.get(user["subscription_type"], SUBSCRIPTION_PLANS.get("free", {}))
    has_limit, used, limit = check_generation_limit(uid)

    until = user["subscription_until"] or "—"
    await message.answer(
        "👤 Профиль\n\n"
        f"ID: {user['user_id']}\n"
        f"Username: @{user['username']}\n"
        f"Имя: {user['first_name']}\n\n"
        f"Подписка: {plan.get('emoji','')} {plan.get('name', user['subscription_type'])}\n"
        f"Действует до: {until}\n"
        f"Лимит: {used}/{limit} (сегодня)\n"
        f"Бонусы: {user['bonus_points']}"
    )


@router.message(F.text == "⚙️ Настройки")
async def btn_settings(message: Message):
    await message.answer("⚙️ Настройки:", reply_markup=settings_kb())


@router.message(F.text == "❓ Помощь")
async def btn_help(message: Message):
    await cmd_help(message)


@router.message(F.text == "💬 Обратная связь")
async def btn_feedback(message: Message):
    await message.answer("💬 Напиши сюда сообщение с багом/идеей — оно попадёт в лог, и можно будет быстро найти проблему.")


# ----------------- Settings handlers -----------------
@router.callback_query(F.data == "nav:settings")
async def nav_settings(query: CallbackQuery):
    await query.message.edit_text("⚙️ Настройки:", reply_markup=settings_kb())
    await query.answer()


@router.callback_query(F.data == "settings:notif")
async def settings_notif(query: CallbackQuery):
    uid = query.from_user.id
    await query.message.edit_text("🔔 Уведомления (нажми, чтобы переключить):", reply_markup=notif_kb(uid))
    await query.answer()


@router.callback_query(F.data.startswith("settings:toggle:"))
async def settings_toggle(query: CallbackQuery):
    uid = query.from_user.id
    field = query.data.split("settings:toggle:")[1]
    toggle_notification(uid, field)
    await query.message.edit_text("🔔 Уведомления (нажми, чтобы переключить):", reply_markup=notif_kb(uid))
    await query.answer("✅ Обновлено")


@router.callback_query(F.data == "settings:saved")
async def settings_saved(query: CallbackQuery):
    uid = query.from_user.id
    rows = get_saved_last(uid, limit=10)
    if not rows:
        await query.answer("Нет сохранённого", show_alert=True)
        return

    text = "📚 Сохранённое (последние 10):\n\n"
    for sid, ctype, content, created_at in rows:
        preview = (content[:140] + "…") if len(content) > 140 else content
        text += f"#{sid} [{ctype}] {created_at}\n{preview}\n\n"

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:settings")]
    ]))
    await query.answer()


@router.callback_query(F.data == "settings:export")
async def settings_export(query: CallbackQuery):
    uid = query.from_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT content_type, prompt, content, created_at
    FROM generation_history
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT 500
    """, (uid,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await query.answer("Нет данных для экспорта", show_alert=True)
        return

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["content_type", "prompt", "content", "created_at"])
    for r in rows:
        writer.writerow(list(r))

    data = buf.getvalue().encode("utf-8")
    filename = f"contentgpt_export_{uid}.csv"
    await query.message.answer_document(BufferedInputFile(data, filename=filename))
    await query.answer("✅ Экспорт отправлен")


# ----------------- Subscriptions / payments -----------------
def subscriptions_kb() -> InlineKeyboardMarkup:
    # Покажем basic/premium/vip если они есть в конфиге.
    buttons = []
    for key in ("basic", "premium", "vip"):
        if key not in SUBSCRIPTION_PLANS:
            continue
        plan = SUBSCRIPTION_PLANS[key]
        name = f"{plan.get('emoji','')} {plan.get('name', key)}"
        price = plan.get("price", 0)
        buttons.append([
            InlineKeyboardButton(text=f"{name} (Касса, {price}₽)", callback_data=f"pay:yk:{key}"),
            InlineKeyboardButton(text=f"{name} (Stars, {price})", callback_data=f"pay:stars:{key}"),
        ])
    if not buttons:
        buttons = [[InlineKeyboardButton(text="Нет планов в конфиге", callback_data="noop")]]

    return InlineKeyboardMarkup(inline_keyboard=buttons + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:genmenu")]])


@router.message(F.text == "💎 Подписки")
async def btn_subscriptions(message: Message):
    await message.answer("💎 Подписки: выбери план и способ оплаты.", reply_markup=subscriptions_kb())


@router.callback_query(F.data == "noop")
async def noop(query: CallbackQuery):
    await query.answer()


@router.callback_query(F.data.startswith("pay:yk:"))
async def pay_yookassa(query: CallbackQuery):
    uid = query.from_user.id
    sub_type = query.data.split("pay:yk:")[1]
    plan = SUBSCRIPTION_PLANS.get(sub_type)
    if not plan:
        await query.answer("❌ План не найден", show_alert=True)
        return

    amount = float(plan.get("price", 0))
    if amount <= 0:
        await query.answer("❌ Некорректная цена", show_alert=True)
        return

    # Создаём заказ и платёж через твой handler
    order_id = str(uuid.uuid4())

    await query.answer("⏳ Создаю платёж...")
    payment = await asyncio.to_thread(
        kassa.create_payment,
        amount,
        f"Подписка {plan.get('name', sub_type)}",
        order_id
    )

    if not payment or payment.get("status") != "success":
        await query.message.edit_text(f"❌ Не удалось создать платёж.\n{payment}")
        return

    payment_id = payment.get("payment_id")
    url = payment.get("confirmation_url")
    if not payment_id or not url:
        await query.message.edit_text("❌ Ошибка: нет payment_id/confirmation_url в ответе.")
        return

    # пишем в БД pending
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO payments (user_id, provider, external_id, order_id, subscription_type, amount, currency, status)
    VALUES (?, 'yookassa', ?, ?, ?, ?, 'RUB', 'pending')
    """, (uid, str(payment_id), order_id, sub_type, amount))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить картой", url=url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"pay:ykcheck:{payment_id}:{sub_type}")],
    ])

    await query.message.edit_text(
        "💳 Оплата через YooKassa\n\n"
        f"План: {plan.get('emoji','')} {plan.get('name', sub_type)}\n"
        f"Сумма: {amount} ₽\n\n"
        "После оплаты вернись в чат и нажми «✅ Я оплатил».",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("pay:ykcheck:"))
async def pay_yookassa_check(query: CallbackQuery):
    uid = query.from_user.id
    _, rest = query.data.split("pay:ykcheck:", 1)
    payment_id, sub_type = rest.split(":", 1)

    await query.answer("⏳ Проверяю платёж...")

    status_resp = await asyncio.to_thread(kassa.get_payment_status, payment_id)
    if not status_resp or status_resp.get("status") != "success":
        await query.answer("❌ Не удалось проверить платёж", show_alert=True)
        return

    pay_status = status_resp.get("payment_status")
    if pay_status not in ("succeeded", "waiting_for_capture"):
        await query.answer(f"Статус: {pay_status}. Если только оплатил — подожди 10–20 сек и нажми ещё раз.", show_alert=True)
        return

    # Активируем подписку
    update_subscription(uid, sub_type, days=30)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE payments SET status='completed', updated_at=datetime('now')
    WHERE user_id=? AND provider='yookassa' AND external_id=?
    """, (uid, str(payment_id)))
    conn.commit()
    conn.close()

    plan = SUBSCRIPTION_PLANS.get(sub_type, {})
    await query.message.edit_text(
        "✅ Платёж подтверждён!\n\n"
        f"Активирована подписка: {plan.get('emoji','')} {plan.get('name', sub_type)}\n"
        "Срок: 30 дней\n\n"
        "Можешь пользоваться генерацией."
    )
    await query.answer("✅ Готово")


@router.callback_query(F.data.startswith("pay:stars:"))
async def pay_stars(query: CallbackQuery):
    uid = query.from_user.id
    sub_type = query.data.split("pay:stars:")[1]
    plan = SUBSCRIPTION_PLANS.get(sub_type)
    if not plan:
        await query.answer("❌ План не найден", show_alert=True)
        return

    # Для Stars удобно держать цену в целых Stars.
    amount_stars = int(plan.get("price", 0))
    if amount_stars <= 0:
        await query.answer("❌ Некорректная цена", show_alert=True)
        return

    payload = json.dumps({"sub_type": sub_type, "user_id": uid, "nonce": str(uuid.uuid4())})
    prices = [LabeledPrice(label=f"{plan.get('name', sub_type)}", amount=amount_stars)]

    # provider_token для Stars обычно пустой
    await bot.send_invoice(
        chat_id=uid,
        title=f"Подписка {plan.get('name', sub_type)}",
        description="Оплата Telegram Stars",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="contentgpt_subscription"
    )
    await query.answer("✅ Инвойс отправлен")


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    uid = message.from_user.id
    sp = message.successful_payment

    try:
        payload = json.loads(sp.invoice_payload)
        sub_type = payload.get("sub_type")
        if not sub_type:
            await message.answer("✅ Платёж получен, но не удалось определить план (payload).")
            return

        update_subscription(uid, sub_type, days=30)

        # В Stars total_amount приходит в “минимальных единицах”; для XTR это обычно целые Stars.
        amount = float(sp.total_amount)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO payments (user_id, provider, external_id, order_id, subscription_type, amount, currency, status)
        VALUES (?, 'telegram_stars', ?, NULL, ?, ?, 'XTR', 'completed')
        """, (uid, sp.telegram_payment_charge_id, sub_type, amount))
        conn.commit()
        conn.close()

        plan = SUBSCRIPTION_PLANS.get(sub_type, {})
        await message.answer(
            "✅ Подписка активирована!\n\n"
            f"{plan.get('emoji','')} {plan.get('name', sub_type)}\n"
            f"Сумма: {int(amount)} Stars\n"
            "Срок: 30 дней"
        )
    except Exception as e:
        logger.exception("successful_payment error: {}", e)
        await message.answer("✅ Платёж получен, но произошла ошибка при активации. Напиши в поддержку.")


# ----------------- Generation flow -----------------
@router.callback_query(F.data == "nav:genmenu")
async def nav_genmenu(query: CallbackQuery):
    await query.message.edit_text("📝 Выбери тип генерации:", reply_markup=generation_menu_kb())
    await query.answer()


@router.callback_query(F.data.startswith("gen:"))
async def gen_router(query: CallbackQuery, state: FSMContext):
    uid = query.from_user.id
    has_limit, used, limit = check_generation_limit(uid)
    if not has_limit:
        await query.answer(f"❌ Лимит исчерпан ({used}/{limit})", show_alert=True)
        return

    kind = query.data.split("gen:")[1]

    if kind == "post":
        await query.message.edit_text("📝 Пост: введи тему (например: «путешествия»).")
        await state.set_state(GenStates.post_topic)

    elif kind == "caption":
        await query.message.edit_text("💬 Подпись: пришли фото (как изображение).")
        await state.set_state(GenStates.caption_photo)

    elif kind == "story":
        await query.message.edit_text("📱 История: выбери вектор/цель (например: «прогрев», «продажа», «вовлечение»).")
        await state.set_state(GenStates.story_vector)

    elif kind == "ideas":
        await query.message.edit_text("💡 Идеи: укажи нишу/тему (например: «фитнес для занятых»).")
        await state.set_state(GenStates.ideas_theme)

    elif kind == "style":
        await query.message.edit_text("🤖 Мой стиль: пришли 2–3 примера твоих постов одним сообщением.")
        await state.set_state(GenStates.style_examples)

    else:
        await query.answer("❌ Неизвестный тип", show_alert=True)

    await query.answer()


@router.message(GenStates.post_topic)
async def post_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text.strip())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😎 Лёгкий/юмор", callback_data="poststyle:fun")],
        [InlineKeyboardButton(text="💼 Профи", callback_data="poststyle:pro")],
        [InlineKeyboardButton(text="📢 Продающий", callback_data="poststyle:sales")],
        [InlineKeyboardButton(text="🔥 Вирусный", callback_data="poststyle:viral")],
    ])
    await message.answer("Шаг 2/4: выбери стиль:", reply_markup=kb)
    await state.set_state(GenStates.post_style)


@router.callback_query(F.data.startswith("poststyle:"), GenStates.post_style)
async def post_style(query: CallbackQuery, state: FSMContext):
    style = query.data.split("poststyle:")[1]
    await state.update_data(style=style)
    await query.message.edit_text("Шаг 3/4: напиши целевую аудиторию (например: «предприниматели»).")
    await state.set_state(GenStates.post_audience)
    await query.answer()


@router.message(GenStates.post_audience)
async def post_audience(message: Message, state: FSMContext):
    await state.update_data(audience=message.text.strip())
    await message.answer("Шаг 4/4: напиши CTA (например: «подпишись», «напиши в ЛС», «оставь комментарий»).")
    await state.set_state(GenStates.post_cta)


@router.message(GenStates.post_cta)
async def post_cta(message: Message, state: FSMContext):
    uid = message.from_user.id
    data = await state.get_data()
    topic = data.get("topic", "")
    style = data.get("style", "pro")
    audience = data.get("audience", "")
    cta = message.text.strip()

    user_style = get_user_style(uid)
    style_note = f"\nСтиль автора (учти): {user_style}\n" if user_style else ""

    prompt = (
        f"Создай пост для соцсетей.\n"
        f"Тема: {topic}\n"
        f"Аудитория: {audience}\n"
        f"Стиль: {style}\n"
        f"CTA: {cta}\n"
        f"Длина: 800–1200 знаков.\n"
        f"Добавь структуру (абзацы/списки), эмодзи уместно.\n"
        f"{style_note}"
    )

    await message.answer("⏳ Генерирую...")
    text = await gpt.generate(prompt, "post")
    if not text:
        await message.answer("❌ Не удалось сгенерировать. Проверь YANDEX_GPT_API_KEY/FOLDER_ID.")
        await state.clear()
        return

    increment_generation_counter(uid)
    save_generation(uid, "post", prompt, text)
    last_content[uid] = {"content_type": "post", "prompt": prompt, "content": text}

    await message.answer(text, reply_markup=after_generation_kb())
    await state.clear()


@router.message(GenStates.story_vector)
async def story_vector(message: Message, state: FSMContext):
    uid = message.from_user.id
    vector = message.text.strip()

    user_style = get_user_style(uid)
    style_note = f"\nСтиль автора (учти): {user_style}\n" if user_style else ""

    prompt = (
        f"Сгенерируй сценарий сторис.\n"
        f"Цель/вектор: {vector}\n"
        f"Формат: 5–7 слайдов, на каждом: текст + что показать + вопрос/CTA.\n"
        f"{style_note}"
    )

    await message.answer("⏳ Генерирую...")
    text = await gpt.generate(prompt, "story")
    if not text:
        await message.answer("❌ Не удалось сгенерировать. Проверь YANDEX_GPT_API_KEY/FOLDER_ID.")
        await state.clear()
        return

    increment_generation_counter(uid)
    save_generation(uid, "story", prompt, text)
    last_content[uid] = {"content_type": "story", "prompt": prompt, "content": text}

    await message.answer(text, reply_markup=after_generation_kb())
    await state.clear()


@router.message(GenStates.ideas_theme)
async def ideas_theme(message: Message, state: FSMContext):
    uid = message.from_user.id
    theme = message.text.strip()

    user_style = get_user_style(uid)
    style_note = f"\nСтиль автора (учти): {user_style}\n" if user_style else ""

    prompt = (
        f"Дай 10 идей контента.\n"
        f"Тема/ниша: {theme}\n"
        f"Сделай идеи разными по формату: пост, сторис, рилс, карусель, опрос.\n"
        f"{style_note}"
    )

    await message.answer("⏳ Генерирую...")
    text = await gpt.generate(prompt, "ideas")
    if not text:
        await message.answer("❌ Не удалось сгенерировать. Проверь YANDEX_GPT_API_KEY/FOLDER_ID.")
        await state.clear()
        return

    increment_generation_counter(uid)
    save_generation(uid, "ideas", prompt, text)
    last_content[uid] = {"content_type": "ideas", "prompt": prompt, "content": text}

    await message.answer(text, reply_markup=after_generation_kb())
    await state.clear()


@router.message(GenStates.caption_photo)
async def caption_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Пришли фото как изображение (не файлом).")
        return

    # Caption без Vision — просто фиксируем факт фото и спрашиваем задачу.
    # (Если захочешь — добавим Vision обратно отдельным модулем, но чтобы не ломать прод, здесь минимально.)
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("Ок. Теперь напиши задачу для подписи (тон, цель, оффер, длина).")
    await state.set_state(GenStates.caption_task)


@router.message(GenStates.caption_task)
async def caption_task(message: Message, state: FSMContext):
    uid = message.from_user.id
    data = await state.get_data()
    task = message.text.strip()

    user_style = get_user_style(uid)
    style_note = f"\nСтиль автора (учти): {user_style}\n" if user_style else ""

    prompt = (
        "Сгенерируй подпись к посту в соцсетях.\n"
        "Дай 2 версии: формальная и неформальная.\n"
        "Добавь 10 хештегов.\n"
        f"ТЗ пользователя: {task}\n"
        f"{style_note}"
    )

    await message.answer("⏳ Генерирую...")
    text = await gpt.generate(prompt, "caption")
    if not text:
        await message.answer("❌ Не удалось сгенерировать. Проверь YANDEX_GPT_API_KEY/FOLDER_ID.")
        await state.clear()
        return

    increment_generation_counter(uid)
    save_generation(uid, "caption", prompt, text)
    last_content[uid] = {"content_type": "caption", "prompt": prompt, "content": text}

    await message.answer(text, reply_markup=after_generation_kb())
    await state.clear()


@router.message(GenStates.style_examples)
async def style_examples(message: Message, state: FSMContext):
    uid = message.from_user.id
    examples = message.text.strip()

    prompt = (
        "Проанализируй стиль автора по примерам.\n"
        "Скажи: тон, структура, длина, любимые приемы, 3-5 характерных фраз.\n"
        "Ответ: 3-5 предложений + 5 буллетов.\n\n"
        f"ПРИМЕРЫ:\n{examples}"
    )

    await message.answer("⏳ Анализирую стиль...")
    style = await gpt.generate(prompt, "style_analysis")
    if not style:
        await message.answer("❌ Не удалось проанализировать стиль.")
        await state.clear()
        return

    increment_generation_counter(uid)
    save_user_style(uid, style)

    await message.answer(
        "✅ Стиль сохранён!\n\n"
        f"{style}\n\n"
        "Теперь генерация будет учитывать твой стиль."
    )
    await state.clear()


# ----------------- Content actions: save/edit/regen -----------------
@router.callback_query(F.data == "content:save")
async def content_save(query: CallbackQuery):
    uid = query.from_user.id
    item = last_content.get(uid)
    if not item:
        await query.answer("Нет контента для сохранения", show_alert=True)
        return

    save_content(uid, item["content_type"], item["prompt"], item["content"])
    await query.answer("✅ Сохранено")


@router.callback_query(F.data == "content:regen")
async def content_regen(query: CallbackQuery):
    uid = query.from_user.id
    item = last_content.get(uid)
    if not item:
        await query.answer("Нет контента для перегенерации", show_alert=True)
        return

    has_limit, used, limit = check_generation_limit(uid)
    if not has_limit:
        await query.answer(f"❌ Лимит исчерпан ({used}/{limit})", show_alert=True)
        return

    await query.answer("⏳ Генерирую ещё вариант...")
    text = await gpt.generate(item["prompt"], item["content_type"])
    if not text:
        await query.message.answer("❌ Не удалось перегенерировать.")
        return

    increment_generation_counter(uid)
    save_generation(uid, item["content_type"], item["prompt"], text)
    last_content[uid]["content"] = text

    await query.message.answer(text, reply_markup=after_generation_kb())


@router.callback_query(F.data == "content:edit")
async def content_edit(query: CallbackQuery, state: FSMContext):
    uid = query.from_user.id
    item = last_content.get(uid)
    if not item:
        await query.answer("Нет контента для правок", show_alert=True)
        return

    await state.update_data(edit_base_prompt=item["prompt"], edit_content_type=item["content_type"])
    await query.message.answer("✏️ Напиши, какие правки внести (тон, структура, длина, что добавить/убрать).")
    await state.set_state(EditStates.waiting_edit)
    await query.answer()


@router.message(EditStates.waiting_edit)
async def edit_apply(message: Message, state: FSMContext):
    uid = message.from_user.id
    has_limit, used, limit = check_generation_limit(uid)
    if not has_limit:
        await message.answer(f"❌ Лимит исчерпан ({used}/{limit}).")
        await state.clear()
        return

    data = await state.get_data()
    base_prompt = data.get("edit_base_prompt", "")
    ctype = data.get("edit_content_type", "post")
    instr = message.text.strip()

    prompt = base_prompt + "\n\nВнеси правки (обязательно): " + instr

    await message.answer("⏳ Применяю правки...")
    text = await gpt.generate(prompt, ctype)
    if not text:
        await message.answer("❌ Не удалось применить правки.")
        await state.clear()
        return

    increment_generation_counter(uid)
    save_generation(uid, ctype, prompt, text)
    last_content[uid] = {"content_type": ctype, "prompt": prompt, "content": text}

    await message.answer(text, reply_markup=after_generation_kb())
    await state.clear()


# ----------------- Admin -----------------
@router.message(F.text == "👨‍💼 Админ-панель")
async def admin_panel(message: Message):
    uid = message.from_user.id
    if not is_user_admin(uid):
        await message.answer("❌ Доступ запрещён.")
        return

    s = admin_stats()
    await message.answer(
        "👨‍💼 Админ-панель\n\n"
        f"Пользователей: {s['total_users']}\n"
        f"Платящих: {s['paid_users']}\n"
        f"Генераций: {s['generations']}\n"
        f"Платежей (completed): {s['completed_payments']}\n"
        f"Выручка (условно): {s['revenue']}\n"
    )


# ----------------- Main -----------------
async def main():
    logger.info("🚀 Starting bot...")
    init_database()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())