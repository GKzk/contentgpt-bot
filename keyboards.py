# keyboards/main_menu.py - клавиатуры для меню бота
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# ==================== ОСНОВНОЕ МЕНЮ ====================

def get_main_menu() -> ReplyKeyboardMarkup:
    """Основное меню бота"""
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🤖 AI Генератор"),
                KeyboardButton(text="📊 Мой профиль")
            ],
            [
                KeyboardButton(text="⭐ Подписка"),
                KeyboardButton(text="🎁 Бонусы")
            ],
            [
                KeyboardButton(text="❓ Помощь"),
                KeyboardButton(text="⚙️ Настройки")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return kb

# ==================== AI ГЕНЕРАТОР ====================

def get_ai_menu() -> InlineKeyboardMarkup:
    """Меню выбора типа контента для генерации"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 Пост для соцсетей", callback_data="content_social_post"),
                InlineKeyboardButton(text="📢 Рекламный слоган", callback_data="content_ad_slogan")
            ],
            [
                InlineKeyboardButton(text="📝 Описание товара", callback_data="content_description"),
                InlineKeyboardButton(text="💡 Идеи контента", callback_data="content_ideas")
            ],
            [
                InlineKeyboardButton(text="❓ Ответ на FAQ", callback_data="content_faq"),
                InlineKeyboardButton(text="✨ Анализ текста", callback_data="content_analyze")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")
            ]
        ]
    )
    return kb

# ==================== ПОДПИСКИ ====================

def get_subscription_menu() -> InlineKeyboardMarkup:
    """Меню выбора подписки"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Basic ($2.99/мес)", callback_data="subscribe_basic"),
                InlineKeyboardButton(text="💎 Premium ($7.99/мес)", callback_data="subscribe_premium")
            ],
            [
                InlineKeyboardButton(text="👑 VIP ($19.99/мес)", callback_data="subscribe_vip")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")
            ]
        ]
    )
    return kb

def get_payment_method_menu() -> InlineKeyboardMarkup:
    """Меню выбора метода оплаты"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Карта (Stripe)", callback_data="payment_card"),
                InlineKeyboardButton(text="🏦 Яндекс.Касса", callback_data="payment_yandex")
            ],
            [
                InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="payment_stars")
            ],
            [
                InlineKeyboardButton(text="◀️ Отмена", callback_data="back_subscription")
            ]
        ]
    )
    return kb

# ==================== ПРОФИЛЬ ====================

def get_profile_menu() -> InlineKeyboardMarkup:
    """Меню профиля"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="profile_stats"),
                InlineKeyboardButton(text="🔄 Мою подписку", callback_data="profile_subscription")
            ],
            [
                InlineKeyboardButton(text="🎁 Реферальная программа", callback_data="profile_referral"),
                InlineKeyboardButton(text="💰 История платежей", callback_data="profile_payments")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")
            ]
        ]
    )
    return kb

# ==================== БОНУСЫ ====================

def get_loyalty_menu() -> InlineKeyboardMarkup:
    """Меню лояльности и бонусов"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Мои бонусы", callback_data="loyalty_balance"),
                InlineKeyboardButton(text="🎫 Как заработать?", callback_data="loyalty_how")
            ],
            [
                InlineKeyboardButton(text="🛍️ Использовать бонусы", callback_data="loyalty_use"),
                InlineKeyboardButton(text="📊 История", callback_data="loyalty_history")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")
            ]
        ]
    )
    return kb

# ==================== ПОМОЩЬ ====================

def get_help_menu() -> InlineKeyboardMarkup:
    """Меню помощи"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❓ FAQ", callback_data="help_faq"),
                InlineKeyboardButton(text="📖 Документация", callback_data="help_docs")
            ],
            [
                InlineKeyboardButton(text="💬 Обратная связь", callback_data="help_feedback"),
                InlineKeyboardButton(text="🐛 Сообщить об ошибке", callback_data="help_bug")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")
            ]
        ]
    )
    return kb

# ==================== СОЦИАЛЬНЫЕ СЕТИ ====================

def get_social_platform_menu() -> InlineKeyboardMarkup:
    """Меню выбора платформы для поста"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📷 Instagram", callback_data="platform_instagram"),
                InlineKeyboardButton(text="🎬 TikTok", callback_data="platform_tiktok")
            ],
            [
                InlineKeyboardButton(text="📘 Facebook", callback_data="platform_facebook"),
                InlineKeyboardButton(text="🐦 Twitter/X", callback_data="platform_twitter")
            ],
            [
                InlineKeyboardButton(text="💼 LinkedIn", callback_data="platform_linkedin"),
                InlineKeyboardButton(text="👥 VKontakte", callback_data="platform_vk")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_ai_menu")
            ]
        ]
    )
    return kb

# ==================== ПОДТВЕРЖДЕНИЕ ====================

def get_confirmation_menu(action_name: str = "действие") -> InlineKeyboardMarkup:
    """Меню подтверждения"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_no")
            ]
        ]
    )
    return kb

# ==================== ИНЛАЙН МЕНЮ ДЛЯ РЕЗУЛЬТАТОВ ====================

def get_content_actions_menu(content_id: str) -> InlineKeyboardMarkup:
    """Меню действий с сгенерированным контентом"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Копировать", callback_data=f"copy_content_{content_id}"),
                InlineKeyboardButton(text="🔄 Переделать", callback_data=f"regenerate_{content_id}")
            ],
            [
                InlineKeyboardButton(text="💾 Сохранить", callback_data=f"save_{content_id}"),
                InlineKeyboardButton(text="📤 Поделиться", callback_data=f"share_{content_id}")
            ],
            [
                InlineKeyboardButton(text="🆕 Новый контент", callback_data="back_ai_menu"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")
            ]
        ]
    )
    return kb

# ==================== РЕФЕРАЛЬНАЯ ПРОГРАММА ====================

def get_referral_menu() -> InlineKeyboardMarkup:
    """Меню реферальной программы"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Поделиться ссылкой", callback_data="referral_share"),
                InlineKeyboardButton(text="👥 Мои рефералы", callback_data="referral_list")
            ],
            [
                InlineKeyboardButton(text="💰 Заработок", callback_data="referral_earnings"),
                InlineKeyboardButton(text="📖 Как это работает?", callback_data="referral_info")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_profile")
            ]
        ]
    )
    return kb

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_back_button(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    """Простая кнопка назад"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)]
        ]
    )
    return kb

def get_inline_url_button(text: str, url: str) -> InlineKeyboardMarkup:
    """Кнопка с ссылкой"""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, url=url)]
        ]
    )
    return kb
