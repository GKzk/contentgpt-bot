# config.py - КОНФИГУРАЦИЯ БОТА (ИСПРАВЛЕННАЯ ВЕРСИЯ)

import os
import sys
from dotenv import load_dotenv
from pydantic import BaseSettings  # ← ВАЖНО: ДОБАВЛЕНО!
from loguru import logger

# ==================== ЗАГРУЗКА .ENV ====================

env_path = os.path.join(os.path.dirname(__file__), '.env')
logger.info(f"🔍 Ищу файл .env в: {env_path}")

if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info("✅ Файл .env найден и загружен")
else:
    logger.warning(f"⚠️ Файл .env не найден в {env_path}")

# ==================== ПОДПИСКИ ====================

SUBSCRIPTION_PLANS = {
    'free': {
        'name': 'Free',
        'emoji': '🎯',
        'price': 0,
        'price_rub': 0,
        'monthly_limit': 5,
        'description': 'Идеально для тестирования'
    },
    'basic': {
        'name': 'Basic',
        'emoji': '⭐',
        'price': 222,
        'price_rub': 222,
        'monthly_limit': 100,
        'description': '100 запросов в день'
    },
    'premium': {
        'name': 'Premium',
        'emoji': '💎',
        'price': 593,
        'price_rub': 593,
        'monthly_limit': 500,
        'description': '500 запросов в день'
    },
    'vip': {
        'name': 'VIP',
        'emoji': '👑',
        'price': 1484,
        'price_rub': 1484,
        'monthly_limit': 9999,
        'description': 'Безлимитные запросы'
    }
}

# ==================== НАСТРОЙКИ ====================

class Settings(BaseSettings):
    """Конфигурация приложения"""
    
    # ==================== TELEGRAM ====================
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    
    # ==================== YANDEX GPT ====================
    YANDEX_API_KEY: str = os.getenv("YANDEX_API_KEY", "")
    YANDEX_FOLDER_ID: str = os.getenv("YANDEX_FOLDER_ID", "")
    
    # ==================== ПЛАТЕЖИ (НОВОЕ В V3) ====================
    YANDEX_KASSA_SHOP_ID: str = os.getenv("YANDEX_KASSA_SHOP_ID", "")
    YANDEX_KASSA_SECRET_KEY: str = os.getenv("YANDEX_KASSA_SECRET_KEY", "")
    PAYMENT_WEBHOOK_URL: str = os.getenv("PAYMENT_WEBHOOK_URL", "")
    
    # ==================== ЦЕНЫ ====================
    PRICE_BASIC_MONTHLY: int = int(os.getenv("PRICE_BASIC_MONTHLY", "22230"))
    PRICE_PREMIUM_MONTHLY: int = int(os.getenv("PRICE_PREMIUM_MONTHLY", "59310"))
    PRICE_VIP_MONTHLY: int = int(os.getenv("PRICE_VIP_MONTHLY", "148410"))
    
    # ==================== ЛИМИТЫ ====================
    FREE_MESSAGES_LIMIT: int = int(os.getenv("FREE_MESSAGES_LIMIT", "5"))
    BASIC_MESSAGES_LIMIT: int = int(os.getenv("BASIC_MESSAGES_LIMIT", "100"))
    PREMIUM_MESSAGES_LIMIT: int = int(os.getenv("PREMIUM_MESSAGES_LIMIT", "500"))
    VIP_MESSAGES_LIMIT: int = int(os.getenv("VIP_MESSAGES_LIMIT", "9999"))
    
    # ==================== БД ====================
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot_database.db")
    
    # ==================== ЛОГИРОВАНИЕ ====================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = '.env'
        case_sensitive = True
    
    @classmethod
    def validate(cls):
        """Проверить конфигурацию"""
        errors = []
        
        # ==================== ОБЯЗАТЕЛЬНЫЕ ПРОВЕРКИ ====================
        
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("❌ TELEGRAM_BOT_TOKEN не установлен")
        
        if not cls.ADMIN_ID:
            errors.append("❌ ADMIN_ID не установлен")
        
        if not cls.YANDEX_API_KEY:
            errors.append("❌ YANDEX_API_KEY не установлен")
        
        if not cls.YANDEX_FOLDER_ID:
            errors.append("❌ YANDEX_FOLDER_ID не установлен")
        
        # ==================== ОПЦИОНАЛЬНЫЕ ПРОВЕРКИ (ПЛАТЕЖИ) ====================
        
        if not cls.YANDEX_KASSA_SHOP_ID:
            errors.append("⚠️ YANDEX_KASSA_SHOP_ID не установлен (платежи не будут работать)")
        
        if not cls.YANDEX_KASSA_SECRET_KEY:
            errors.append("⚠️ YANDEX_KASSA_SECRET_KEY не установлен (платежи не будут работать)")
        
        # ==================== ВЫВОД ОШИБОК ====================
        
        if errors:
            # Обязательные ошибки
            critical_errors = [e for e in errors if e.startswith("❌")]
            # Предупреждения
            warnings = [e for e in errors if e.startswith("⚠️")]
            
            # Показываем всё
            for error in errors:
                if error.startswith("❌"):
                    logger.error(error)
                else:
                    logger.warning(error)
            
            # Если есть критичные ошибки - выходим
            if critical_errors:
                logger.error("\n❌ КРИТИЧНЫЕ ОШИБКИ - БОТ НЕ ЗАПУСТИТСЯ!\n")
                sys.exit(1)
        else:
            logger.info("✅ Конфигурация валидна")

# ==================== СОЗДАНИЕ ЭКЗЕМПЛЯРА ====================

settings = Settings()
settings.validate()

# ==================== ИНФОРМАЦИЯ О КОНФИГУРАЦИИ ====================

logger.info(f"""
═══════════════════════════════════════════
        ✅ БОТ ГОТОВ К ЗАПУСКУ
═══════════════════════════════════════════

🤖 Telegram Bot ID: {settings.ADMIN_ID}
🔐 YandexGPT API: {'✅ Подключен' if settings.YANDEX_API_KEY else '❌ Не подключен'}
💳 Платежи: {'✅ Подключены' if settings.YANDEX_KASSA_SHOP_ID else '⚠️ Не подключены'}

📊 Подписки:
• Free: {SUBSCRIPTION_PLANS['free']['monthly_limit']} запросов/день (Бесплатно)
• Basic: {SUBSCRIPTION_PLANS['basic']['monthly_limit']} запросов/день ({SUBSCRIPTION_PLANS['basic']['price']}₽)
• Premium: {SUBSCRIPTION_PLANS['premium']['monthly_limit']} запросов/день ({SUBSCRIPTION_PLANS['premium']['price']}₽)
• VIP: Безлимит ({SUBSCRIPTION_PLANS['vip']['price']}₽)

═══════════════════════════════════════════
""")