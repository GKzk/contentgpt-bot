# database_models.py V2 - РАБОТА С БАЗОЙ ДАННЫХ SQLITE (ПОЛНАЯ ВЕРСИЯ)
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from loguru import logger

class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.create_tables()
    
    def get_connection(self):
        """Получить подключение к базе данных"""
        return sqlite3.connect(self.db_path)
    
    def create_tables(self):
        """Создать таблицы базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                subscription_type TEXT DEFAULT 'free',
                subscription_end TEXT,
                messages_count INTEGER DEFAULT 0,
                messages_today INTEGER DEFAULT 0,
                last_message_date TEXT,
                bonus_points INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0.0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица истории использования
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                request_type TEXT,
                prompt TEXT,
                response TEXT,
                tokens_used INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица платежей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                currency TEXT,
                subscription_type TEXT,
                payment_status TEXT,
                payment_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица сохранённого контента
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content_type TEXT,
                content TEXT,
                title TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица настроек пользователя
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                notifications_enabled BOOLEAN DEFAULT 1,
                notifications_features BOOLEAN DEFAULT 1,
                notifications_promos BOOLEAN DEFAULT 1,
                notifications_reminders BOOLEAN DEFAULT 1,
                statistics_collection BOOLEAN DEFAULT 1,
                show_in_rating BOOLEAN DEFAULT 0,
                save_history BOOLEAN DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица реферралов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                bonus_given BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")
    
    def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Добавить нового пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, first_name, last_name))
            
            # Создаём настройки пользователя
            cursor.execute("""
                INSERT OR IGNORE INTO user_settings (user_id)
                VALUES (?)
            """, (user_id,))
            
            conn.commit()
            logger.info(f"✅ Пользователь {user_id} добавлен")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления пользователя: {e}")
        finally:
            conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить данные пользователя"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_user_settings(self, user_id: int) -> Optional[Dict]:
        """Получить настройки пользователя"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_user_settings(self, user_id: int, **kwargs):
        """Обновить настройки пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        allowed_fields = [
            'notifications_enabled', 'notifications_features',
            'notifications_promos', 'notifications_reminders',
            'statistics_collection', 'show_in_rating', 'save_history'
        ]
        
        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if fields:
            set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
            values = list(fields.values()) + [user_id]
            
            cursor.execute(f"""
                UPDATE user_settings
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, values)
            
            conn.commit()
        
        conn.close()
    
    def increment_messages(self, user_id: int):
        """Увеличить счётчик сообщений"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        user = self.get_user(user_id)
        if user:
            last_date = user.get('last_message_date', '')
            
            if last_date != today:
                # Новый день - сбросить счётчик
                cursor.execute("""
                    UPDATE users 
                    SET messages_today = 1, 
                        messages_count = messages_count + 1,
                        last_message_date = ?
                    WHERE user_id = ?
                """, (today, user_id))
            else:
                # Тот же день - увеличить счётчик
                cursor.execute("""
                    UPDATE users 
                    SET messages_today = messages_today + 1,
                        messages_count = messages_count + 1
                    WHERE user_id = ?
                """, (user_id,))
            
            conn.commit()
        
        conn.close()
    
    def can_use_feature(self, user_id: int) -> bool:
        """Проверить, может ли пользователь использовать функцию"""
        user = self.get_user(user_id)
        if not user:
            return False
        
        limit = self.get_messages_limit(user_id)
        return user['messages_today'] < limit
    
    def get_messages_limit(self, user_id: int) -> int:
        """Получить лимит сообщений для пользователя"""
        from config import SUBSCRIPTION_PLANS
        
        user = self.get_user(user_id)
        if not user:
            return 0
        
        subscription_type = user.get('subscription_type', 'free')
        plan = SUBSCRIPTION_PLANS.get(subscription_type, SUBSCRIPTION_PLANS['free'])
        
        return plan.get('monthly_limit', 0)
    
    def add_usage(self, user_id: int, request_type: str, prompt: str, response: str, tokens: int):
        """Добавить запись использования"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO usage_history 
                (user_id, request_type, prompt, response, tokens_used)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, request_type, prompt, response, tokens))
            
            conn.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка добавления истории: {e}")
        finally:
            conn.close()
    
    def save_content(self, user_id: int, content_type: str, content: str, title: str = ""):
        """Сохранить контент"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO saved_content 
                (user_id, content_type, content, title)
                VALUES (?, ?, ?, ?)
            """, (user_id, content_type, content, title))
            
            conn.commit()
            logger.info(f"✅ Контент сохранён для {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
        finally:
            conn.close()
    
    def get_saved_content(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить сохранённый контент"""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM saved_content 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def add_bonus_points(self, user_id: int, points: int, reason: str = ""):
        """Добавить бонусные баллы"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET bonus_points = bonus_points + ?
            WHERE user_id = ?
        """, (points, user_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Начислено {points} баллов пользователю {user_id}: {reason}")
    
    def update_subscription(self, user_id: int, subscription_type: str, duration_days: int = 30):
        """Обновить подписку пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        end_date = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d")
        
        cursor.execute("""
            UPDATE users 
            SET subscription_type = ?,
                subscription_end = ?
            WHERE user_id = ?
        """, (subscription_type, end_date, user_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Подписка {subscription_type} активирована для {user_id} до {end_date}")
    
    def add_referral(self, referrer_id: int, referred_id: int):
        """Добавить реферал"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO referrals (referrer_id, referred_id)
                VALUES (?, ?)
            """, (referrer_id, referred_id))
            
            # Даём бонусы за реферала
            cursor.execute("""
                UPDATE users 
                SET bonus_points = bonus_points + 50
                WHERE user_id = ?
            """, (referrer_id,))
            
            conn.commit()
            logger.info(f"✅ Реферал добавлен: {referrer_id} -> {referred_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления реферала: {e}")
        finally:
            conn.close()
    
    def get_referral_count(self, user_id: int) -> int:
        """Получить количество рефералов"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def add_payment(self, user_id: int, amount: float, subscription_type: str, status: str = "completed"):
        """Добавить запись платежа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO payments 
                (user_id, amount, currency, subscription_type, payment_status)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, amount, "RUB", subscription_type, status))
            
            # Обновляем общий потраченный бюджет
            cursor.execute("""
                UPDATE users 
                SET total_spent = total_spent + ?
                WHERE user_id = ?
            """, (amount, user_id))
            
            conn.commit()
            logger.info(f"✅ Платёж добавлен: {user_id}, {amount}₽")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления платежа: {e}")
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict:
        """Получить общую статистику"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(messages_count) FROM users")
        total_messages = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(total_spent) FROM users")
        total_revenue = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
        new_users_today = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_users": total_users,
            "total_messages": total_messages,
            "total_revenue": total_revenue,
            "new_users_today": new_users_today
        }

# Глобальный экземпляр
db = Database()