# main.py - главная точка входа для бота
import asyncio
from itertools import product
import logging
from aiogram import Bot, Dispatcher, F # type: ignore
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
import sys

# Импортируем конфиг и БД
from config import settings
from database_models import db
from keyboards import (
    get_main_menu, get_ai_menu, get_subscription_menu,
    get_profile_menu, get_loyalty_menu, get_help_menu,
    get_social_platform_menu, get_content_actions_menu,
    get_confirmation_menu, get_back_button
)
from yandex_api import yandex_gpt_handler as ai_handler


# ==================== ЛОГИРОВАНИЕ ====================
logger.remove()
logger.add(
    sys.stderr,
    format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL
)
logger.add("bot_logs.log", rotation="500 MB", retention="10 days")

# ==================== СОСТОЯНИЯ FSM ====================
class Form(StatesGroup):
    """Состояния для управления диалогом"""
    waiting_for_topic = State()
    waiting_for_platform = State()
    waiting_for_product = State()
    waiting_for_audience = State()
    waiting_for_text = State()
    waiting_for_payment = State()

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Проверяем конфиг при старте
settings.validate()

# ==================== КОМАНДЫ ====================

@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    
    # Добавляем пользователя в БД
    db.add_user(user_id, username, first_name, last_name)
    
    logger.info(f"✅ Новый пользователь: {first_name} (@{username})")
    
    welcome_text = f"""
👋 Добро пожаловать, {first_name}!

Я - AI Генератор Контента 🤖, ваш персональный помощник в создании креативного контента для любых нужд.

🎯 Что я умею:
• 📱 Писать посты для социальных сетей (Instagram, TikTok, Facebook и т.д.)
• 📢 Создавать рекламные слоганы и копирайт
• 📝 Писать описания товаров
• 💡 Генерировать идеи для контента
• ❓ Отвечать на часто задаваемые вопросы
• ✨ Анализировать и улучшать текст

💳 Я предлагаю гибкую систему подписок:
• 🎯 Basic - $2.99/месяц
• 💎 Premium - $7.99/месяц  
• 👑 VIP - $19.99/месяц

🎁 Новые пользователи получают {settings.FREE_MESSAGES_LIMIT} бесплатных запросов в день!

Начнем? Выберите, что вам нужно:
"""
    
    await message.answer(welcome_text, reply_markup=get_main_menu())
    await state.clear()

@dp.message(Command("help"))
async def help_command(message: Message):
    """Обработчик команды /help"""
    help_text = """
❓ СПРАВКА ПО БОТУ

📱 ОСНОВНЫЕ ФУНКЦИИ:
• /start - Начать работу
• /profile - Мой профиль
• /stats - Статистика использования
• /subscription - Управление подпиской
• /help - Эта справка

🤖 КАК ИСПОЛЬЗОВАТЬ AI:
1. Нажмите "🤖 AI Генератор"
2. Выберите тип контента
3. Напишите описание/тему
4. Получите результат!

💳 ПОДПИСКИ:
• Бесплатная: 5 запросов/день
• Basic: 100 запросов/день
• Premium: 500 запросов/день
• VIP: Неограниченно

🎁 БОНУСЫ:
• Каждая покупка = +100 бонусов
• За приглашение друга = +50 бонусов
• Используйте бонусы для скидок

📧 КОНТАКТЫ:
• Поддержка: support@example.com
• Коммьюнити: https://t.me/yourcommunity

Есть вопросы? Напишите в поддержку!
"""
    
    await message.answer(help_text, reply_markup=get_back_button())

@dp.message(Command("profile"))
async def profile_command(message: Message):
    """Показать профиль пользователя"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Нажмите /start")
        return
    
    from config import SUBSCRIPTION_PLANS
    subscription = SUBSCRIPTION_PLANS.get(user['subscription_type'], {})
    
    profile_text = f"""
👤 ВАШ ПРОФИЛЬ

📊 Основная информация:
• Пользователь: {user['first_name']}
• ID: {user_id}
• Регистрация: {user['created_at'][:10]}

⭐ Подписка: {subscription.get('emoji', '')} {subscription.get('name', 'Бесплатная')}
• Лимит запросов/день: {user['messages_today']}/{subscription.get('monthly_limit', 0)}
• Всего запросов: {user['messages_count']}
• Потрачено: ${user['total_spent']:.2f}

🎁 Бонусы: {user['bonus_points']} ⭐

📈 Статистика:
• Активен: {'Да ✅' if user['is_active'] else 'Нет ❌'}
• Последнее использование: {user['updated_at'][:10]}
"""
    
    if user['subscription_type'] != 'free' and user['subscription_end']:
        profile_text += f"• Подписка до: {user['subscription_end']}\n"
    
    await message.answer(profile_text, reply_markup=get_profile_menu())

# ==================== ОСНОВНОЕ МЕНЮ ====================

@dp.message(F.text == "🤖 AI Генератор")
async def ai_generator_menu(message: Message):
    """Меню AI генератора"""
    user_id = message.from_user.id
    
    if not db.can_use_feature(user_id):
        await message.answer(
            "⛔ Вы достигли лимита запросов на сегодня.\n"
            "Обновите подписку для большего количества запросов.",
            reply_markup=get_subscription_menu()
        )
        return
    
    await message.answer(
        "🤖 Выберите тип контента для генерации:",
        reply_markup=get_ai_menu()
    )

@dp.message(F.text == "📊 Мой профиль")
async def profile_menu(message: Message):
    """Меню профиля"""
    await profile_command(message)

@dp.message(F.text == "⭐ Подписка")
async def subscription_menu(message: Message):
    """Меню подписок"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    from config import SUBSCRIPTION_PLANS
    
    subs_text = "💳 ВЫБЕРИТЕ ПОДПИСКУ:\n\n"
    
    for key, plan in SUBSCRIPTION_PLANS.items():
        subs_text += f"{plan['emoji']} {plan['name']}\n"
        subs_text += f"   💰 {plan['price'] // 100} руб/месяц\n"
        subs_text += f"   📊 {plan['monthly_limit']} запросов/день\n\n"
    
    if user['subscription_type'] != 'free':
        subs_text += f"✅ Ваша текущая подписка: {user['subscription_type']}\n"
    
    await message.answer(subs_text, reply_markup=get_subscription_menu())

@dp.message(F.text == "🎁 Бонусы")
async def loyalty_menu(message: Message):
    """Меню бонусов"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    loyalty_text = f"""
🎁 СИСТЕМА БОНУСОВ И ЛОЯЛЬНОСТИ

⭐ Ваши бонусы: {user['bonus_points']}

💰 КАК ЗАРАБОТАТЬ:
• Каждая покупка подписки = +100 бонусов
• Приглашение друга = +50 бонусов
• Положительный отзыв = +25 бонусов
• Ежедневный вход = +1 бонус

🛍️ ЧТО МОЖНО ПОЛУЧИТЬ:
• 100 бонусов = $1 скидка
• 500 бонусов = месяц Basic
• 1000 бонусов = месяц Premium
• 2500 бонусов = месяц VIP

💡 Совет: Используйте бонусы стратегически!
"""
    
    await message.answer(loyalty_text, reply_markup=get_loyalty_menu())

@dp.message(F.text == "❓ Помощь")
async def help_menu(message: Message):
    """Меню помощи"""
    await help_command(message)

@dp.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message):
    """Меню настроек"""
    settings_text = """
⚙️ НАСТРОЙКИ

Здесь вы можете настроить:
• Язык интерфейса
• Уведомления
• Приватность данных
• Удалить аккаунт

Что вас интересует?
"""
    await message.answer(settings_text, reply_markup=get_help_menu())

# ==================== AI КОНТЕНТ ====================

@dp.callback_query(F.data == "content_social_post")
async def social_post_handler(query: CallbackQuery, state: FSMContext):
    """Обработчик выбора "Пост для соцсетей" """
    await query.message.edit_text(
        "📱 Выберите социальную сеть:",
        reply_markup=get_social_platform_menu()
    )
    await state.set_state(Form.waiting_for_platform)

@dp.callback_query(F.data.startswith("platform_"))
async def platform_selected(query: CallbackQuery, state: FSMContext):
    """Пользователь выбрал платформу"""
    platform = query.data.split("_")[1]
    platform_names = {
        "instagram": "Instagram",
        "tiktok": "TikTok",
        "facebook": "Facebook",
        "twitter": "Twitter/X",
        "linkedin": "LinkedIn",
        "vk": "VKontakte"
    }
    
    await state.update_data(platform=platform_names.get(platform, platform))
    await state.set_state(Form.waiting_for_topic)
    
    await query.message.edit_text(
        f"📝 Напишите тему для поста в {platform_names.get(platform, platform)}:\n\n"
        "Например: Как начать фриланс, Советы по фотографии и т.д."
    )

@dp.message(Form.waiting_for_topic)
async def topic_received(message: Message, state: FSMContext):
    """Получена тема для контента"""
    user_id = message.from_user.id
    
    if not db.can_use_feature(user_id):
        await message.answer(
            "⛔ Вы достигли лимита запросов на сегодня.\n"
            "Обновите подписку для большего количества запросов."
        )
        await state.clear()
        return
    
    data = await state.get_data()
    platform = data.get('platform', 'Instagram')
    topic = message.text
    
    # Показываем "печать" (работает)
    processing_msg = await message.answer("⏳ Генерирую контент для вас... Подождите минутку 🤖")
    
    try:
        # Вызываем OpenAI
        result = await ai_handler.generate_ad_slogan(product, audience) # type: ignore
        
        if result:
            # Увеличиваем счетчик сообщений
            db.increment_messages(user_id)
            db.add_usage(user_id, "social_post", topic, result, 100)
            
            # Удаляем сообщение "печать"
            await processing_msg.delete()
            
            # Отправляем результат
            result_text = f"""
✅ ГОТОВО! Вот ваш пост для {platform}:

{result}

═══════════════════════════════════════

Вам нравится? Вы можете:
• Скопировать текст
• Переделать его
• Создать новый пост
"""
            
            await message.answer(result_text, reply_markup=get_content_actions_menu("1"))
        else:
            await processing_msg.delete()
            await message.answer(
                "❌ Ошибка при генерации контента. Попробуйте позже.",
                reply_markup=get_ai_menu()
            )
    
    except Exception as e:
        logger.error(f"Ошибка при генерации: {str(e)}")
        await processing_msg.delete()
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    await state.clear()

@dp.callback_query(F.data == "content_ad_slogan")
async def ad_slogan_handler(query: CallbackQuery, state: FSMContext):
    """Обработчик "Рекламный слоган" """
    await query.message.edit_text(
        "📢 Напишите название вашего продукта или услуги:\n\n"
        "Например: Кофейня 'Арома', Курс по Python и т.д."
    )
    await state.set_state(Form.waiting_for_product)

@dp.message(Form.waiting_for_product)
async def product_received(message: Message, state: FSMContext):
    """Получено название продукта"""
    user_id = message.from_user.id
    
    if not db.can_use_feature(user_id):
        await message.answer("⛔ Вы достигли лимита запросов на сегодня.")
        await state.clear()
        return
    
    product = message.text
    await state.update_data(product=product)
    await state.set_state(Form.waiting_for_audience)
    
    await message.answer(
        "👥 Теперь опишите вашу целевую аудиторию:\n\n"
        "Например: Женщины 25-40 лет, интересующиеся здоровьем"
    )

@dp.message(Form.waiting_for_audience)
async def audience_received(message: Message, state: FSMContext):
    """Получена информация об аудитории"""
    user_id = message.from_user.id
    
    if not db.can_use_feature(user_id):
        await message.answer("⛔ Вы достигли лимита запросов на сегодня.")
        await state.clear()
        return
    
    data = await state.get_data()
    product = data.get('product')
    audience = message.text  # ← ПОЛУЧАЕМ ТЕКСТ ОТ ПОЛЬЗОВАТЕЛЯ
    
    # Генерируем
    processing_msg = await message.answer("⏳ Создаю рекламные слоганы... 🎯")
    
    try:
        result = await ai_handler.generate_ad_slogan(product, audience)
        
        if result:
            db.increment_messages(user_id)
            db.add_usage(user_id, "ad_slogan", f"{product} для {audience}", result, 80)
            
            await processing_msg.delete()
            
            result_text = f"""
✅ ГОТОВО! Вот рекламные слоганы для "{product}":

{result}

═══════════════════════════════════════
Нравятся слоганы? Используйте их в своей рекламе! 📢
"""
            
            await message.answer(result_text, reply_markup=get_content_actions_menu("2"))
        else:
            await processing_msg.delete()
            await message.answer("❌ Ошибка при создании слоганов. Попробуйте позже.")
    
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await processing_msg.delete()
        await message.answer("❌ Произошла ошибка.")
    
    await state.clear()

# ==================== CALLBACK ОБРАБОТЧИКИ ====================

@dp.callback_query(F.data == "back_main")
async def back_to_main(query: CallbackQuery):
    """Вернуться в главное меню"""
    await query.message.edit_text(
        "🏠 Главное меню:",
        reply_markup=get_main_menu()
    )

@dp.callback_query(F.data == "back_ai_menu")
async def back_to_ai(query: CallbackQuery):
    """Вернуться в меню AI"""
    await query.message.edit_text(
        "🤖 Выберите тип контента:",
        reply_markup=get_ai_menu()
    )

# ==================== ОБРАБОТКА ПЛАТЕЖЕЙ ====================

@dp.callback_query(F.data.startswith("subscribe_"))
async def subscribe_handler(query: CallbackQuery, state: FSMContext):
    """Обработчик выбора подписки"""
    subscription_type = query.data.split("_")[1]
    
    from config import SUBSCRIPTION_PLANS
    plan = SUBSCRIPTION_PLANS.get(subscription_type)
    
    if not plan:
        await query.answer("❌ Подписка не найдена", show_alert=True)
        return
    
    price = plan['price'] // 100
    
    payment_text = f"""
💳 ОФОРМЛЕНИЕ ПОДПИСКИ

Подписка: {plan['emoji']} {plan['name']}
Стоимость: ${price / 100:.2f} или {price} руб
Запросов в день: {plan['monthly_limit']}

Как хотите оплатить?
"""
    
    await state.update_data(subscription_type=subscription_type, amount=price)
    await query.message.edit_text(payment_text)
    
    # Здесь интегрируется реальная система платежей
    # Для примера показываем кнопки
    await query.message.answer(
        "Выберите способ оплаты:",
        reply_markup=InlineKeyboardMarkup( # type: ignore
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Карта (Stripe)", callback_data="pay_card")], # type: ignore
                [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="pay_stars")], # type: ignore
                [InlineKeyboardButton(text="◀️ Отмена", callback_data="back_main")] # type: ignore
            ]
        )
    )

# ==================== ОСНОВНОЙ ЦИКЛ ====================

async def main():
    """Главная функция"""
    logger.info("🚀 Запуск бота...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {str(e)}")
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())
