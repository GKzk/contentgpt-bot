# main_v4_final_fixed_all.py - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ

import asyncio
import sqlite3
import os
import uuid
import json
import requests
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from config import settings, SUBSCRIPTION_PLANS, CONTENT_TYPES
from yandex_kassa_handler import kassa

# ==================== ИНИЦИАЛИЗАЦИЯ ====================

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

user_cache = {}
logger.add("bot.log", rotation="500 MB", retention="10 days")

# ==================== FSM STATES ====================

class GenerationStates(StatesGroup):
    """Состояния для многоэтапной генерации"""
    waiting_for_post_topic = State()
    waiting_for_post_style = State()
    waiting_for_post_audience = State()
    waiting_for_post_cta = State()
    
    waiting_for_caption_choice = State()
    waiting_for_caption_text = State()
    waiting_for_caption_photo = State()
    
    waiting_for_story_vector = State()
    waiting_for_ideas_theme = State()
    
    admin_view_user_id = State()

# ==================== BOTTOM KEYBOARD ====================

def get_bottom_keyboard():
    """Нижняя панель с основными командами"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Генерация"),
                KeyboardButton(text="💎 Подписки"),
            ],
            [
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="👤 Профиль"),
            ],
            [
                KeyboardButton(text="❓ Помощь"),
                KeyboardButton(text="💬 Обратная связь"),
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_admin_bottom_keyboard():
    """Нижняя панель для админов"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Генерация"),
                KeyboardButton(text="💎 Подписки"),
            ],
            [
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="👤 Профиль"),
            ],
            [
                KeyboardButton(text="❓ Помощь"),
                KeyboardButton(text="👨‍💼 Админ-панель"),
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# ==================== YANDEX GPT ====================

class YandexGPTHandler:
    """Обработчик для YandexGPT API"""
    
    API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    
    def __init__(self):
        self.api_key = settings.YANDEX_GPT_API_KEY
        self.folder_id = settings.YANDEX_GPT_FOLDER_ID
    
    def generate_content(self, prompt: str, content_type: str = "post"):
        """Генерировать контент через YandexGPT"""
        
        if not self.api_key or not self.folder_id:
            logger.error("❌ YandexGPT не настроен")
            return None
        
        system_prompts = {
            "post": "Ты профессиональный копирайтер для социальных сетей. Создаёшь привлекающие посты с эмодзи, интересными фактами и призывом к действию.",
            "caption": "Ты эксперт по подписям к фото. Создаёшь две версии подписи - формальную и неформальную, с релевантными хештегами.",
            "story": "Ты креативный специалист по Stories. Генерируешь интересные, динамичные идеи для Instagram/TikTok Stories с вопросами для engagement.",
            "ideas": "Ты креативный генератор идей. Создаёшь оригинальные, практичные идеи для контента.",
        }
        
        system_prompt = system_prompts.get(content_type, system_prompts["post"])
        
        payload = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": "1500"
            },
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": prompt}
            ]
        }
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            response = requests.post(self.API_URL, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'alternatives' in data['result']:
                    return data['result']['alternatives'][0]['message']['text']
            else:
                logger.error(f"❌ YandexGPT ошибка: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка генерации: {e}")
            return None

gpt = YandexGPTHandler()

# ==================== DATABASE ====================

def init_database():
    """Инициализация БД"""
    try:
        conn = sqlite3.connect(settings.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(generation_history)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()
        
        if columns and 'prompt' not in columns:
            logger.warning("⚠️ Старая БД - обновляем...")
            backup_path = f"{settings.DATABASE_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(settings.DATABASE_PATH, backup_path)
    except:
        pass
    
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            subscription_type TEXT DEFAULT 'free',
            subscription_until TIMESTAMP,
            bonus_points INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generation_counter (
            user_id INTEGER PRIMARY KEY,
            date TEXT,
            count INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            notif_features INTEGER DEFAULT 1,
            notif_promos INTEGER DEFAULT 1,
            notif_reminders INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            subscription_type TEXT,
            status TEXT,
            payment_system TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content_type TEXT,
            content TEXT,
            prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content_type TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

# ==================== DATABASE FUNCTIONS ====================

def get_or_create_user(user_id: int, username: str = "", first_name: str = ""):
    """Получить или создать пользователя"""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, subscription_type)
            VALUES (?, ?, ?, 'free')
        """, (user_id, username, first_name))
        
        cursor.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
        conn.commit()
        logger.info(f"✅ Новый пользователь: {user_id}")
    
    conn.close()

def get_user_info(user_id: int) -> dict:
    """Получить информацию пользователя"""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT user_id, username, first_name, subscription_type, subscription_until, bonus_points
        FROM users WHERE user_id = ?
    """, (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'user_id': result[0],
            'username': result[1],
            'first_name': result[2],
            'subscription_type': result[3],
            'subscription_until': result[4],
            'bonus_points': result[5]
        }
    return None

def get_daily_generation_limit(user_id: int) -> int:
    """Получить лимит генераций на день"""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT subscription_type FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        sub_type = result[0]
        plan = SUBSCRIPTION_PLANS.get(sub_type, SUBSCRIPTION_PLANS['free'])
        conn.close()
        return plan['monthly_limit']
    
    conn.close()
    return SUBSCRIPTION_PLANS['free']['monthly_limit']

def check_generation_limit(user_id: int) -> tuple:
    """Проверить лимит генераций - ИСПРАВЛЕНО"""
    is_admin = is_user_admin(user_id)
    
    if is_admin:
        return True, 0, 999999
    
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    limit = get_daily_generation_limit(user_id)
    
    cursor.execute("""
        SELECT count FROM generation_counter 
        WHERE user_id = ? AND date = ?
    """, (user_id, today))
    
    result = cursor.fetchone()
    used = result[0] if result else 0
    
    conn.close()
    
    has_limit = used < limit
    return has_limit, used, limit

def increment_generation_counter(user_id: int):
    """Увеличить счётчик генераций"""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("""
        INSERT OR REPLACE INTO generation_counter (user_id, date, count)
        VALUES (?, ?, COALESCE((
            SELECT count FROM generation_counter 
            WHERE user_id = ? AND date = ?
        ), 0) + 1)
    """, (user_id, today, user_id, today))
    
    conn.commit()
    conn.close()

def is_user_admin(user_id: int) -> bool:
    """Проверить администратор ли пользователь"""
    if user_id == settings.ADMIN_ID:
        return True
    
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return bool(result and result[0])

def save_generated_content(user_id: int, content_type: str, content: str, prompt: str = ""):
    """Сохранить генерированный контент"""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO generation_history (user_id, content_type, content, prompt)
        VALUES (?, ?, ?, ?)
    """, (user_id, content_type, content, prompt))
    
    conn.commit()
    conn.close()
    user_cache[f"{user_id}_last_{content_type}"] = content

def get_admin_stats() -> dict:
    """Получить статистику для админа"""
    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_type != 'free'")
    paid_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'completed'")
    total_revenue = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM generation_history")
    total_generations = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*), SUM(amount) FROM payments 
        WHERE status = 'completed' AND created_at > datetime('now', '-7 days')
    """)
    result = cursor.fetchone()
    payments_7d = result[0] if result else 0
    revenue_7d = result[1] if result and result[1] else 0
    
    cursor.execute("""
        SELECT subscription_type, COUNT(*) FROM users 
        GROUP BY subscription_type
    """)
    subscriptions = dict(cursor.fetchall())
    
    conn.close()
    
    return {
        'total_users': total_users,
        'paid_users': paid_users,
        'total_revenue': total_revenue,
        'total_generations': total_generations,
        'payments_7d': payments_7d,
        'revenue_7d': revenue_7d,
        'subscriptions': subscriptions
    }

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@router.message(Command("start"))
async def start_handler(message: Message):
    """Команда /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "не указан"
    first_name = message.from_user.first_name or "Пользователь"
    
    get_or_create_user(user_id, username, first_name)
    
    has_limit, used, limit = check_generation_limit(user_id)
    limit_text = f"📊 Лимит: {used}/{limit}" if not is_user_admin(user_id) else "📊 Безлимит"
    
    welcome_text = f"""
╔════════════════════════════════════════╗
║  🚀 CONTENTGPT BOT v4.0                ║
║  Генерация контента с YandexGPT        ║
╚════════════════════════════════════════╝

👋 Привет, {first_name}!

{limit_text}

Используй кнопки ниже для навигации!
"""
    
    kb = get_admin_bottom_keyboard() if is_user_admin(user_id) else get_bottom_keyboard()
    
    await message.answer(welcome_text, reply_markup=kb)
    logger.info(f"✅ Пользователь {user_id} запустил бота")

# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ КНОПОК ====================

@router.message(F.text == "📝 Генерация")
async def text_generation_menu(message: Message):
    """Меню генерации из текстовой кнопки - ИСПРАВЛЕНО"""
    user_id = message.from_user.id
    has_limit, used, limit = check_generation_limit(user_id)
    
    if not has_limit:
        await message.answer(f"❌ Лимит исчерпан ({used}/{limit})")
        return
    
    limit_text = f"📊 Использовано: {used}/{limit}" if not is_user_admin(user_id) else "📊 Безлимит"
    
    text = f"""
📝 **ГЕНЕРАЦИЯ КОНТЕНТА**

{limit_text}

Выбери тип:
"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Пост", callback_data="gen_post_start")],
        [InlineKeyboardButton(text="💬 Подпись к фото", callback_data="gen_caption_start")],
        [InlineKeyboardButton(text="📱 История", callback_data="gen_story_start")],
        [InlineKeyboardButton(text="💡 Идеи", callback_data="gen_ideas_start")],
    ])
    
    await message.answer(text, reply_markup=kb)

@router.message(F.text == "👤 Профиль")
async def text_profile(message: Message):
    """Профиль из текстовой кнопки - ИСПРАВЛЕНО"""
    user_id = message.from_user.id
    
    user = get_user_info(user_id)
    has_limit, used, limit = check_generation_limit(user_id)
    
    if user:
        plan = SUBSCRIPTION_PLANS.get(user['subscription_type'], SUBSCRIPTION_PLANS['free'])
        
        text = f"""
👤 **ВАШ ПРОФИЛЬ**

📱 ID: {user['user_id']}
📝 Username: @{user['username']}
👤 Имя: {user['first_name']}

💎 **ПОДПИСКА:**
{plan['emoji']} {plan['name']}
📊 Лимит: {used}/{plan['monthly_limit']} генераций (сегодня)
"""
        
        if user['subscription_until']:
            text += f"⏳ Действует до: {user['subscription_until']}\n"
        
        text += f"\n🎁 Бонусы: {user['bonus_points']}"
    else:
        text = "❌ Профиль не найден"
    
    await message.answer(text)

@router.message(F.text == "⚙️ Настройки")
async def text_settings(message: Message):
    """Настройки из текстовой кнопки"""
    text = """
⚙️ **НАСТРОЙКИ**

Доступные функции:
- 🔔 Управление уведомлениями
- 📥 Экспорт данных
- 📚 Сохранённый контент

Напишите то, что хотите настроить!
"""
    
    await message.answer(text)

@router.message(F.text == "💎 Подписки")
async def text_subscriptions(message: Message):
    """Подписки из текстовой кнопки - ИСПРАВЛЕНО"""
    user_id = message.from_user.id
    
    text = """
💎 **ТАРИФНЫЕ ПЛАНЫ**

🎯 Free: 5 запросов/день (0₽)
⭐ Basic: 100 запросов/день (79₽/мес)
💎 Premium: 500 запросов/день (159₽/мес)
👑 VIP: 9999 запросов/день (229₽/мес)

Выбери план:
"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Basic (79₽)", callback_data="buy_basic")],
        [InlineKeyboardButton(text="💎 Premium (159₽)", callback_data="buy_premium")],
        [InlineKeyboardButton(text="👑 VIP (229₽)", callback_data="buy_vip")],
    ])
    
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("buy_"))
async def buy_subscription(query: CallbackQuery):
    """Покупка подписки - ИСПРАВЛЕНО"""
    user_id = query.from_user.id
    
    subscription_map = {
        "buy_basic": ("basic", 79),
        "buy_premium": ("premium", 159),
        "buy_vip": ("vip", 229)
    }
    
    sub_type, amount = subscription_map.get(query.data, ("basic", 79))
    plan = SUBSCRIPTION_PLANS.get(sub_type, SUBSCRIPTION_PLANS['free'])
    
    try:
        # Создаём платёж через Яндекс.Касса
        payment = kassa.create_payment(
            amount=amount,
            description=f"Подписка {plan['name']}",
            metadata={
                "user_id": user_id,
                "subscription_type": sub_type,
                "bot": "contentgpt"
            }
        )
        
        if payment:
            payment_url = payment.confirmation.confirmation_url
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_subscriptions")],
            ])
            
            await query.message.edit_text(
                f"""
💳 **ОПЛАТА ПОДПИСКИ**

{plan['emoji']} {plan['name']}: {amount}₽

Нажмите кнопку оплаты ↓
""",
                reply_markup=kb
            )
            
            logger.info(f"✅ Платёж создан: {user_id}, {amount}₽, {sub_type}")
        else:
            await query.answer("❌ Ошибка при создании платежа", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Ошибка платежа: {e}")
        await query.answer("❌ Ошибка системы платежей", show_alert=True)

@router.callback_query(F.data == "back_subscriptions")
async def back_subscriptions(query: CallbackQuery):
    """Назад к подпискам"""
    await text_subscriptions(query.message)

@router.message(F.text == "❓ Помощь")
async def text_help(message: Message):
    """Помощь"""
    text = """
❓ **СПРАВКА**

📝 **ГЕНЕРАЦИЯ:**
- Посты в 4 этапа
- Подписи с хештегами
- Истории с выбором вектора
- Идеи для контента

💎 **ПОДПИСКИ:**
Разные лимиты генераций в день

⚙️ **НАСТРОЙКИ:**
Управление уведомлениями и данными

Есть вопросы? Напишите нам!
"""
    
    await message.answer(text)

@router.message(F.text == "💬 Обратная связь")
async def text_feedback(message: Message):
    """Обратная связь"""
    text = """
💬 **ОБРАТНАЯ СВЯЗЬ**

Нам важно твоё мнение! 

Что тебе нравится? Что улучшить?
Есть проблемы?

Напиши нам свои предложения!
"""
    
    await message.answer(text)

@router.message(F.text == "👨‍💼 Админ-панель")
async def text_admin_panel(message: Message):
    """Админ-панель из текстовой кнопки"""
    user_id = message.from_user.id
    
    if not is_user_admin(user_id):
        await message.answer("❌ Доступ запрещён")
        return
    
    stats = get_admin_stats()
    
    text = f"""
👨‍💼 **АДМИН-ПАНЕЛЬ**

📊 **СТАТИСТИКА:**

👥 Пользователей: {stats['total_users']}
💳 Платящих: {stats['paid_users']}
💰 Доход: {stats['total_revenue']}₽
📝 Генераций: {stats['total_generations']}

📈 **За 7 дней:**
💳 Платежей: {stats['payments_7d']}
💰 Доход: {stats['revenue_7d']}₽

🎯 **Подписки:**
"""
    
    for sub_type, count in stats['subscriptions'].items():
        plan = SUBSCRIPTION_PLANS.get(sub_type, {})
        text += f"{plan.get('emoji', '')} {plan.get('name', sub_type)}: {count}\n"
    
    await message.answer(text)

# ==================== ГЕНЕРАЦИЯ ПОСТОВ ====================

@router.callback_query(F.data == "gen_post_start")
async def gen_post_start(query: CallbackQuery, state: FSMContext):
    """Начало генерации поста"""
    user_id = query.from_user.id
    
    has_limit, used, limit = check_generation_limit(user_id)
    if not has_limit:
        await query.answer(f"❌ Лимит исчерпан ({used}/{limit})", show_alert=True)
        return
    
    text = """
📝 **ГЕНЕРАЦИЯ ПОСТА**

**Шаг 1 из 4:** Введите тему поста

Примеры: "путешествия", "здоровье", "бизнес"
"""
    
    await query.message.edit_text(text)
    await state.set_state(GenerationStates.waiting_for_post_topic)

@router.message(GenerationStates.waiting_for_post_topic)
async def post_topic_handler(message: Message, state: FSMContext):
    """Получить тему поста"""
    topic = message.text
    await state.update_data(post_topic=topic)
    
    text = """
📝 **ГЕНЕРАЦИЯ ПОСТА**

**Шаг 2 из 4:** Выберите стиль

Нажмите кнопку:
"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😎 Cool/Funny", callback_data="style_cool")],
        [InlineKeyboardButton(text="💼 Профессиональный", callback_data="style_pro")],
        [InlineKeyboardButton(text="📢 Продающий", callback_data="style_sales")],
        [InlineKeyboardButton(text="🔥 Вирусный", callback_data="style_viral")],
    ])
    
    await message.answer(text, reply_markup=kb)
    await state.set_state(GenerationStates.waiting_for_post_style)

@router.callback_query(GenerationStates.waiting_for_post_style)
async def post_style_handler(query: CallbackQuery, state: FSMContext):
    """Получить стиль поста"""
    style_map = {
        "style_cool": "cool/funny",
        "style_pro": "профессиональный",
        "style_sales": "продающий",
        "style_viral": "вирусный"
    }
    
    style = style_map.get(query.data, "cool")
    await state.update_data(post_style=style)
    
    text = """
📝 **ГЕНЕРАЦИЯ ПОСТА**

**Шаг 3 из 4:** Целевая аудитория

Напишите кто ваша целевая аудитория.

Примеры: "молодые мамы", "предприниматели", "студенты"
"""
    
    await query.message.edit_text(text)
    await state.set_state(GenerationStates.waiting_for_post_audience)

@router.message(GenerationStates.waiting_for_post_audience)
async def post_audience_handler(message: Message, state: FSMContext):
    """Получить аудиторию"""
    audience = message.text
    await state.update_data(post_audience=audience)
    
    text = """
📝 **ГЕНЕРАЦИЯ ПОСТА**

**Шаг 4 из 4:** Призыв к действию (CTA)

Что вы хотите чтобы сделала аудитория?

Примеры: "купить", "подписаться", "комментировать"
"""
    
    await message.answer(text)
    await state.set_state(GenerationStates.waiting_for_post_cta)

@router.message(GenerationStates.waiting_for_post_cta)
async def post_cta_handler(message: Message, state: FSMContext):
    """Получить CTA и генерировать пост"""
    user_id = message.from_user.id
    cta = message.text
    
    data = await state.get_data()
    topic = data.get('post_topic', '')
    style = data.get('post_style', 'cool')
    audience = data.get('post_audience', '')
    
    prompt = f"""
Создай пост для социальных сетей на тему '{topic}' 
для аудитории '{audience}'
в стиле '{style}'
с призывом к действию '{cta}'.

Пост должен быть 200-300 символов, с эмодзи и структурированием.
"""
    
    await message.answer("⏳ Генерирую пост...")
    
    generated = gpt.generate_content(prompt, "post")
    
    if not generated:
        generated = f"❌ Ошибка при генерации. Попробуйте ещё раз."
    else:
        increment_generation_counter(user_id)
        save_generated_content(user_id, "post", generated, prompt)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="save_post")],
        [InlineKeyboardButton(text="🔄 Переделать", callback_data="gen_post_start")],
        [InlineKeyboardButton(text="📝 Новая генерация", callback_data="back_to_generation")],
    ])
    
    await message.answer(generated, reply_markup=kb)
    await state.clear()

# ==================== ГЕНЕРАЦИЯ ПОДПИСЕЙ ====================

@router.callback_query(F.data == "gen_caption_start")
async def gen_caption_start(query: CallbackQuery):
    """Начало генерации подписи"""
    user_id = query.from_user.id
    
    has_limit, used, limit = check_generation_limit(user_id)
    if not has_limit:
        await query.answer(f"❌ Лимит исчерпан ({used}/{limit})", show_alert=True)
        return
    
    text = """
💬 **ГЕНЕРАЦИЯ ПОДПИСИ К ФОТО**

Выберите способ:
"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Описать фото текстом", callback_data="caption_text")],
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="caption_photo")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_generation")],
    ])
    
    await query.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "caption_text")
async def caption_text_choice(query: CallbackQuery, state: FSMContext):
    """Выбрана опция описания текстом"""
    text = """
💬 **ГЕНЕРАЦИЯ ПОДПИСИ**

Опишите что на фото:

Примеры: "девушка на пляже", "завтрак в кафе", "горный пейзаж"
"""
    
    await query.message.edit_text(text)
    await state.update_data(caption_method="text")
    await state.set_state(GenerationStates.waiting_for_caption_text)

@router.message(GenerationStates.waiting_for_caption_text)
async def caption_text_handler(message: Message, state: FSMContext):
    """Получить описание и генерировать подпись"""
    user_id = message.from_user.id
    description = message.text
    
    prompt = f"""
На фото: {description}

Создай 2 варианта подписи к этому фото:

**Вариант 1 (Формальный):**
[профессиональная подпись]

Хештеги: #хештег1 #хештег2 #хештег3 #хештег4 #хештег5 #хештег6 #хештег7 #хештег8 #хештег9 #хештег10

**Вариант 2 (Неформальный):**
[дружеская, веселая подпись]

Хештеги: #хештег1 #хештег2 #хештег3 #хештег4 #хештег5 #хештег6 #хештег7 #хештег8 #хештег9 #хештег10
"""
    
    await message.answer("⏳ Генерирую подписи...")
    
    generated = gpt.generate_content(prompt, "caption")
    
    if not generated:
        generated = "❌ Ошибка при генерации."
    else:
        increment_generation_counter(user_id)
        save_generated_content(user_id, "caption", generated, prompt)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="save_caption")],
        [InlineKeyboardButton(text="🔄 Переделать", callback_data="gen_caption_start")],
        [InlineKeyboardButton(text="📝 Новая генерация", callback_data="back_to_generation")],
    ])
    
    await message.answer(generated, reply_markup=kb)
    await state.clear()

@router.callback_query(F.data == "caption_photo")
async def caption_photo_choice(query: CallbackQuery, state: FSMContext):
    """Выбрана опция загрузки фото"""
    text = """
📸 **ЗАГРУЗКА ФОТО**

Отправьте фото и я создам подписи на его основе:
"""
    
    await query.message.edit_text(text)
    await state.update_data(caption_method="photo")
    await state.set_state(GenerationStates.waiting_for_caption_photo)

@router.message(GenerationStates.waiting_for_caption_photo, F.photo)
async def caption_photo_handler(message: Message, state: FSMContext):
    """Получить фото и генерировать подпись - ИСПРАВЛЕНО"""
    user_id = message.from_user.id
    
    # Генерируем на основе описания (AI не видит само фото)
    # Но просим пользователя дать описание
    text = """
📸 **АНАЛИЗ ФОТО**

Напишите краткое описание что на фото:

Примеры: "девушка в красном платье", "закат на пляже", "тарелка пасты"
"""
    
    await message.answer(text)
    await state.set_state(GenerationStates.waiting_for_caption_text)

@router.message(GenerationStates.waiting_for_caption_photo)
async def caption_photo_error(message: Message):
    """Ошибка - нужно фото"""
    await message.answer("❌ Пожалуйста, отправьте фото (изображение)")

# ==================== ГЕНЕРАЦИЯ ИСТОРИЙ ====================

@router.callback_query(F.data == "gen_story_start")
async def gen_story_start(query: CallbackQuery):
    """Начало генерации истории"""
    user_id = query.from_user.id
    
    has_limit, used, limit = check_generation_limit(user_id)
    if not has_limit:
        await query.answer(f"❌ Лимит исчерпан ({used}/{limit})", show_alert=True)
        return
    
    text = """
📱 **ГЕНЕРАЦИЯ ИСТОРИИ (STORY)**

Выберите вектор истории или рандомную:
"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Свой вектор", callback_data="story_custom")],
        [InlineKeyboardButton(text="🎲 Рандомная", callback_data="story_random")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_generation")],
    ])
    
    await query.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "story_custom")
async def story_custom(query: CallbackQuery, state: FSMContext):
    """Выбрана опция своего вектора"""
    text = """
📱 **ГЕНЕРАЦИЯ ИСТОРИИ**

Опишите вектор истории:

Примеры: "мотивация", "юмор", "образование", "лайфхак", "тренд"
"""
    
    await query.message.edit_text(text)
    await state.update_data(story_type="custom")
    await state.set_state(GenerationStates.waiting_for_story_vector)

@router.callback_query(F.data == "story_random")
async def story_random(query: CallbackQuery):
    """Рандомная история"""
    user_id = query.from_user.id
    
    vectors = ["мотивация", "юмор", "образование", "лайфхак", "трендовое", "развлечение", "полезный совет"]
    vector = random.choice(vectors)
    
    prompt = f"""
Создай 3 идеи для Instagram/TikTok Stories в стиле '{vector}'.

Каждая идея должна содержать:
- **Название идеи**
- **Описание** (как её реализовать)
- **Вопросы для engagement** (3-4 вопроса которые написать в истории)

Используй эмодзи и структурируй красиво!
"""
    
    await query.message.edit_text("⏳ Генерирую идеи для историй...")
    
    generated = gpt.generate_content(prompt, "story")
    
    if not generated:
        generated = "❌ Ошибка при генерации."
    else:
        increment_generation_counter(user_id)
        save_generated_content(user_id, "story", generated, prompt)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="save_story")],
        [InlineKeyboardButton(text="🔄 Переделать", callback_data="gen_story_start")],
        [InlineKeyboardButton(text="📝 Новая генерация", callback_data="back_to_generation")],
    ])
    
    await query.message.answer(generated, reply_markup=kb)

@router.message(GenerationStates.waiting_for_story_vector)
async def story_vector_handler(message: Message, state: FSMContext):
    """Получить вектор и генерировать историю"""
    user_id = message.from_user.id
    vector = message.text
    
    prompt = f"""
Создай 3 идеи для Instagram/TikTok Stories в стиле '{vector}'.

Каждая идея должна содержать:
- **Название идеи**
- **Описание** (как её реализовать)
- **Вопросы для engagement** (3-4 вопроса которые написать в истории)

Используй эмодзи и структурируй красиво!
"""
    
    await message.answer("⏳ Генерирую идеи для историй...")
    
    generated = gpt.generate_content(prompt, "story")
    
    if not generated:
        generated = "❌ Ошибка при генерации."
    else:
        increment_generation_counter(user_id)
        save_generated_content(user_id, "story", generated, prompt)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="save_story")],
        [InlineKeyboardButton(text="🔄 Переделать", callback_data="gen_story_start")],
        [InlineKeyboardButton(text="📝 Новая генерация", callback_data="back_to_generation")],
    ])
    
    await message.answer(generated, reply_markup=kb)
    await state.clear()

# ==================== ГЕНЕРАЦИЯ ИДЕЙ ====================

@router.callback_query(F.data == "gen_ideas_start")
async def gen_ideas_start(query: CallbackQuery, state: FSMContext):
    """Генерация идей"""
    user_id = query.from_user.id
    
    has_limit, used, limit = check_generation_limit(user_id)
    if not has_limit:
        await query.answer(f"❌ Лимит исчерпан ({used}/{limit})", show_alert=True)
        return
    
    text = """
💡 **ГЕНЕРАЦИЯ ИДЕЙ ДЛЯ КОНТЕНТА**

Напишите тему/ниш для которой нужны идеи:

Примеры: "фитнес", "кулинария", "путешествия"
"""
    
    await query.message.edit_text(text)
    await state.set_state(GenerationStates.waiting_for_ideas_theme)

@router.message(GenerationStates.waiting_for_ideas_theme)
async def ideas_theme_handler(message: Message, state: FSMContext):
    """Получить тему и генерировать идеи"""
    user_id = message.from_user.id
    theme = message.text
    
    prompt = f"""
Предложи 5 оригинальных идей для контента в нише '{theme}'.

Каждая идея должна содержать:
- **Название**
- **Описание идеи** (что это)
- **Где поделиться** (инстаграм/тик-ток/ютуб и т.д.)
- **Ожидаемый результат** (какую пользу получит аудитория)

Идеи должны быть практичными и готовыми к реализации.
Используй эмодзи!
"""
    
    await message.answer("⏳ Генерирую идеи...")
    
    generated = gpt.generate_content(prompt, "ideas")
    
    if not generated:
        generated = "❌ Ошибка при генерации."
    else:
        increment_generation_counter(user_id)
        save_generated_content(user_id, "ideas", generated, prompt)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="save_ideas")],
        [InlineKeyboardButton(text="🔄 Переделать", callback_data="gen_ideas_start")],
        [InlineKeyboardButton(text="📝 Новая генерация", callback_data="back_to_generation")],
    ])
    
    await message.answer(generated, reply_markup=kb)
    await state.clear()

# ==================== СОХРАНЕНИЕ КОНТЕНТА ====================

@router.callback_query(F.data.startswith("save_"))
async def save_content_handler(query: CallbackQuery):
    """Сохранить контент"""
    content_type = query.data.split("_")[1]
    user_id = query.from_user.id
    
    last_content = user_cache.get(f"{user_id}_last_{content_type}")
    
    if last_content:
        conn = sqlite3.connect(settings.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO saved_content (user_id, content_type, content)
            VALUES (?, ?, ?)
        """, (user_id, content_type, last_content))
        
        conn.commit()
        conn.close()
    
    await query.answer("✅ Контент сохранён!", show_alert=True)

# ==================== НАВИГАЦИЯ ====================

@router.callback_query(F.data == "back_to_generation")
async def back_to_generation(query: CallbackQuery):
    """Назад в меню генерации"""
    await query.message.edit_text("📝 **ГЕНЕРАЦИЯ КОНТЕНТА**\n\nВыбери тип:")

# ==================== MAIN ====================

async def main():
    """Запуск бота"""
    logger.info("🚀 БОТ V4 ФИНАЛЬНАЯ ВЕРСИЯ ЗАПУСКАЕТСЯ...")
    init_database()
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())