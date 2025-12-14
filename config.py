# config.py - КОНФИГУРАЦИЯ БОТ V3 С YANDEXGPT

import os
from dotenv import load_dotenv
from loguru import logger

# ==================== ЗАГРУЗКА .ENV ====================

env_path = os.path.join(os.path.dirname(__file__), '.env')
logger.info(f"🔍 Ищу файл .env в: {env_path}")

if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info("✅ Файл .env найден и загружен")
else:
    logger.warning(f"⚠️ Файл .env не найден в {env_path}")

# ==================== ОСНОВНЫЕ НАСТРОЙКИ ====================

class Settings:
    """Основные настройки бота"""
    
    # TELEGRAM
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
    
    # БД
    DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")
    
    # ЯНДЕКС.КАССА
    YANDEX_KASSA_SHOP_ID = os.getenv("YANDEX_KASSA_SHOP_ID", "")
    YANDEX_KASSA_SECRET_KEY = os.getenv("YANDEX_KASSA_SECRET_KEY", "")
    PAYMENT_WEBHOOK_URL = os.getenv("PAYMENT_WEBHOOK_URL", "https://yourdomain.com/webhook/yandex")
    YOOKASSA_API_BASE = os.getenv("YOOKASSA_API_BASE", "https://api.yookassa.ru/v3")
    # TELEGRAM STARS
    PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
    
    # CRYPTOMUS (опционально)
    CRYPTOMUS_MERCHANT_ID = os.getenv("CRYPTOMUS_MERCHANT_ID", "")
    CRYPTOMUS_API_KEY = os.getenv("CRYPTOMUS_API_KEY", "")
    CRYPTOMUS_SECRET_KEY = os.getenv("CRYPTOMUS_SECRET_KEY", "")
    
    # YANDEX GPT ⭐ НОВОЕ
    YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY", "")
    YANDEX_GPT_FOLDER_ID = os.getenv("YANDEX_GPT_FOLDER_ID", "")
    
    # РАЗНОЕ
    REQUEST_TIMEOUT = 30
    MAX_MESSAGE_LENGTH = 4096

settings = Settings()

# ==================== ПОДПИСКИ ====================

SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Free",
        "emoji": "🎯",
        "price": 0,
        "price_rub": 0,
        "monthly_limit": 5,
        "description": "Идеально для тестирования",
    },
    "basic": {
        "name": "Basic",
        "emoji": "⭐",
        "price": 79,
        "price_rub": 79,
        "monthly_limit": 100,
        "description": "100 запросов/день",
    },
    "premium": {
        "name": "Premium",
        "emoji": "💎",
        "price": 159,
        "price_rub": 159,
        "monthly_limit": 500,
        "description": "500 запросов/день",
    },
    "vip": {
        "name": "VIP",
        "emoji": "👑",
        "price": 229,
        "price_rub": 229,
        "monthly_limit": 9999,
        "description": "Безлимитные запросы",
    },
}

# ==================== ТИПЫ КОНТЕНТА ====================

CONTENT_TYPES = {
    "post": {
        "name": "Пост",
        "emoji": "📝",
        "description": "Контент для социальных сетей",
    },
    "story": {
        "name": "История",
        "emoji": "📱",
        "description": "Короткий видео-контент",
    },
    "caption": {
        "name": "Подпись",
        "emoji": "💬",
        "description": "Подпись к фото",
    },
    "hashtags": {
        "name": "Хештеги",
        "emoji": "#️⃣",
        "description": "Релевантные хештеги",
    },
    "ideas": {
        "name": "Идеи",
        "emoji": "💡",
        "description": "Идеи для контента",
    },
}

# ==================== ВАЛИДАЦИЯ КОНФИГУРАЦИИ ====================

def validate_config():
    """Проверить конфигурацию"""
    
    logger.info("\n" + "═" * 60)
    logger.info("✅ БОТ V3 ГОТОВ К ЗАПУСКУ")
    logger.info("═" * 60 + "\n")
    
    # Основное
    logger.info("🤖 ОСНОВНОЕ:")
    logger.info(f"• Telegram Bot ID: {settings.ADMIN_ID}")
    if settings.YANDEX_GPT_API_KEY and settings.YANDEX_GPT_FOLDER_ID:
        logger.info("• YandexGPT API: ✅ Подключен")
        logger.info(f"  - Folder ID: {settings.YANDEX_GPT_FOLDER_ID[:20]}...")
    else:
        logger.info("• YandexGPT API: ⚠️ Не подключен")
    
    # Платежи
    logger.info("\n💳 ПЛАТЁЖНЫЕ СИСТЕМЫ:")
    if settings.YANDEX_KASSA_SHOP_ID and settings.YANDEX_KASSA_SECRET_KEY:
        logger.info("• Yandex.Kassa: ✅ Подключена")
    else:
        logger.warning("• Yandex.Kassa: ⚠️ Не подключена")
    
    if settings.PAYMENT_PROVIDER_TOKEN:
        logger.info("• Telegram Stars: ✅ Подключены")
    else:
        logger.warning("• Telegram Stars: ⚠️ Не подключены")
    
    if settings.CRYPTOMUS_MERCHANT_ID and settings.CRYPTOMUS_API_KEY:
        logger.info("• Cryptomus: ✅ Подключена")
    else:
        logger.warning("• Cryptomus: ⚠️ Не подключена")
    
    # Подписки
    logger.info("\n📊 ПОДПИСКИ (НОВЫЕ ЦЕНЫ):")
    for key, plan in SUBSCRIPTION_PLANS.items():
        logger.info(f"• {plan['emoji']} {plan['name']}: {plan['monthly_limit']} запросов/день ({plan['price']}₽)")
    
    logger.info("\n" + "═" * 60 + "\n")

# Запуск валидации
validate_config()

# ==================== ЭКСПОРТ ====================

__all__ = [
    'settings',
    'SUBSCRIPTION_PLANS',
    'CONTENT_TYPES',
    'validate_config',
]