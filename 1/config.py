# config.py - исправленная конфигурация бота
import os
from pathlib import Path
from dotenv import load_dotenv

# ==================== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ====================

# Получаем путь к корню проекта
PROJECT_ROOT = Path(__file__).resolve().parent

# Загружаем переменные из .env файла
env_path = PROJECT_ROOT / ".env"
print(f"🔍 Ищу файл .env в: {env_path}")

if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Файл .env найден и загружен")
else:
    print(f"⚠️ Файл .env не найден в {env_path}")
    print(f"   Текущая директория: {PROJECT_ROOT}")
    print(f"   Файлы в директории: {list(PROJECT_ROOT.glob('*'))}")

# ==================== КЛАСС КОНФИГУРАЦИИ ====================

class Settings:
    """Централизованные настройки приложения"""
    
    # ==================== TELEGRAM ====================
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) if os.getenv("ADMIN_ID") else 0
    
    # ==================== YANDEXGPT API ====================
    YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
    YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
    
    # ==================== OPENAI (ЕСЛИ НУЖЕН) ====================
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1000"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    
    # ==================== ПЛАТЕЖИ ====================
    PAYMENT_CURRENCY = os.getenv("PAYMENT_CURRENCY", "RUB")
    PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
    
    # ==================== ПОДПИСКИ И ЦЕНЫ ====================
    PRICE_BASIC_MONTHLY = int(os.getenv("PRICE_BASIC_MONTHLY", "29900"))
    PRICE_PREMIUM_MONTHLY = int(os.getenv("PRICE_PREMIUM_MONTHLY", "79900"))
    PRICE_VIP_MONTHLY = int(os.getenv("PRICE_VIP_MONTHLY", "199900"))
    
    # ==================== ЛИМИТЫ ====================
    FREE_MESSAGES_LIMIT = int(os.getenv("FREE_MESSAGES_LIMIT", "5"))
    BASIC_MESSAGES_LIMIT = int(os.getenv("BASIC_MESSAGES_LIMIT", "100"))
    PREMIUM_MESSAGES_LIMIT = int(os.getenv("PREMIUM_MESSAGES_LIMIT", "500"))
    VIP_MESSAGES_LIMIT = int(os.getenv("VIP_MESSAGES_LIMIT", "9999"))
    
    # ==================== БАЗА ДАННЫХ ====================
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot_database.db")
    
    # ==================== БОНУСЫ И ЛОЯЛЬНОСТЬ ====================
    BONUS_POINTS_PER_PURCHASE = int(os.getenv("BONUS_POINTS_PER_PURCHASE", "100"))
    LOYALTY_DISCOUNT_PERCENT = float(os.getenv("LOYALTY_DISCOUNT_PERCENT", "0.01"))
    
    # ==================== ЛОГИРОВАНИЕ ====================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # ==================== РЕЖИМ РАБОТЫ ====================
    DEBUG_MODE = os.getenv("DEBUG_MODE", "True").lower() == "true"
    ENABLE_DEBUG_MESSAGES = os.getenv("ENABLE_DEBUG_MESSAGES", "False").lower() == "true"
    
    # ==================== РАЗЛИЧНЫЕ ПАРАМЕТРЫ ====================
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # ==================== ВЫБОР AI ПРОВАЙДЕРА ====================
    AI_PROVIDER = os.getenv("AI_PROVIDER", "yandex")  # "openai", "yandex", "gigachat", "local"
    
    @classmethod
    def validate(cls):
        """Проверка обязательных параметров"""
        
        errors = []
        
        # Проверяем Telegram токен
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("❌ TELEGRAM_BOT_TOKEN не установлен в .env файле")
        
        # Проверяем AI провайдер
        if cls.AI_PROVIDER == "yandex":
            if not cls.YANDEX_API_KEY:
                errors.append("❌ YANDEX_API_KEY не установлен в .env файле")
            if not cls.YANDEX_FOLDER_ID:
                errors.append("❌ YANDEX_FOLDER_ID не установлен в .env файле")
        
        elif cls.AI_PROVIDER == "openai":
            if not cls.OPENAI_API_KEY:
                errors.append("❌ OPENAI_API_KEY не установлен в .env файле")
        
        if errors:
            print("\n⚠️ ОШИБКИ КОНФИГУРАЦИИ:")
            for error in errors:
                print(error)
            raise ValueError("Конфигурация неполная!")
        
        print("✅ Конфигурация валидна")

# ==================== ЦЕНОВЫЕ ТАРИФЫ ====================

SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Бесплатный",
        "price": 0,
        "monthly_limit": Settings.FREE_MESSAGES_LIMIT,
        "emoji": "🎯"
    },
    "basic": {
        "name": "Basic",
        "price": Settings.PRICE_BASIC_MONTHLY,
        "monthly_limit": Settings.BASIC_MESSAGES_LIMIT,
        "emoji": "⭐"
    },
    "premium": {
        "name": "Premium",
        "price": Settings.PRICE_PREMIUM_MONTHLY,
        "monthly_limit": Settings.PREMIUM_MESSAGES_LIMIT,
        "emoji": "💎"
    },
    "vip": {
        "name": "VIP",
        "price": Settings.PRICE_VIP_MONTHLY,
        "monthly_limit": Settings.VIP_MESSAGES_LIMIT,
        "emoji": "👑"
    }
}

# ==================== ТИПЫ ГЕНЕРИРУЕМОГО КОНТЕНТА ====================

CONTENT_TYPES = {
    "social_post": {
        "name": "Пост для соцсетей",
        "prompt_template": "Напиши привлекательный пост для {platform} на тему: {topic}. Максимум {words} слов.",
        "tokens_cost": 50
    },
    "ad_slogan": {
        "name": "Рекламный слоган",
        "prompt_template": "Создай креативный рекламный слоган для продукта: {product}. Целевая аудитория: {audience}.",
        "tokens_cost": 30
    },
    "description": {
        "name": "Описание товара",
        "prompt_template": "Напиши продающее описание для {product_type}: {description}. Стиль: {style}.",
        "tokens_cost": 60
    },
    "ideas": {
        "name": "Идеи контента",
        "prompt_template": "Предложи 5 идей для контента на тему: {topic}. Для аудитории: {audience}.",
        "tokens_cost": 40
    },
    "faq": {
        "name": "FAQ ответ",
        "prompt_template": "Напиши профессиональный ответ на часто задаваемый вопрос: {question}. Контекст: {context}.",
        "tokens_cost": 45
    }
}

# ==================== СОЗДАНИЕ ГЛОБАЛЬНОГО ЭКЗЕМПЛЯРА ====================

settings = Settings()

# Проверяем конфигурацию при загрузке модуля
try:
    settings.validate()
except ValueError as e:
    print(f"❌ Ошибка: {str(e)}")
    # Можно также вывести дополнительную информацию для отладки
    print("\n📋 Текущие значения:")
    print(f"  AI_PROVIDER: {settings.AI_PROVIDER}")
    print(f"  TELEGRAM_BOT_TOKEN: {'✅ установлен' if settings.TELEGRAM_BOT_TOKEN else '❌ НЕ установлен'}")
    print(f"  YANDEX_API_KEY: {'✅ установлен' if settings.YANDEX_API_KEY else '❌ НЕ установлен'}")
    print(f"  YANDEX_FOLDER_ID: {'✅ установлен' if settings.YANDEX_FOLDER_ID else '❌ НЕ установлен'}")
    raise