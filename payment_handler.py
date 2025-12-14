# payment_handler.py - ИНТЕГРАЦИЯ С YANDEX.KASSA И ЛОДЖИКА ОПЛАТЫ

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict
from loguru import logger
import requests
import json
import base64

class PaymentHandler:
    """Обработчик платежей через Yandex.Kassa (ЮKassa)"""
    
    def __init__(self, shop_id: str, secret_key: str):
        """
        shop_id - ID магазина из Yandex.Kassa
        secret_key - Секретный ключ для аутентификации
        """
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.api_url = "https://api.yookassa.ru/v3/payments"
        self.webhook_url = None  # Установите ваш вебхук
    
    def _get_auth_header(self) -> str:
        """Создать заголовок аутентификации"""
        credentials = f"{self.shop_id}:{self.secret_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    async def create_payment(self, user_id: int, amount: float, description: str, subscription_type: str) -> Optional[Dict]:
        """
        Создать платёж в Yandex.Kassa
        
        Args:
            user_id: ID пользователя
            amount: Сумма в рублях (например: 593 для 593₽)
            description: Описание платежа
            subscription_type: Тип подписки (basic, premium, vip)
        
        Returns:
            Dict с информацией о платеже или None при ошибке
        """
        
        try:
            idempotence_key = str(uuid.uuid4())
            
            payload = {
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "payment_method_data": {
                    "type": "bank_card"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://yoursite.com/payment/success"  # ИЗМЕНИТЕ НА ВАШЕ!
                },
                "description": description,
                "metadata": {
                    "user_id": str(user_id),
                    "subscription_type": subscription_type,
                    "order_id": str(uuid.uuid4())
                }
            }
            
            headers = {
                "Authorization": self._get_auth_header(),
                "Content-Type": "application/json",
                "Idempotence-Key": idempotence_key
            }
            
            response = await asyncio.to_thread(
                requests.post,
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Платёж создан для {user_id}: {result['id']}")
                return result
            else:
                logger.error(f"❌ Ошибка создания платежа: {response.status_code}")
                logger.error(f"Ответ: {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"❌ Ошибка: {str(e)}")
            return None
    
    async def get_payment_status(self, payment_id: str) -> Optional[str]:
        """Получить статус платежа"""
        
        try:
            headers = {
                "Authorization": self._get_auth_header(),
                "Content-Type": "application/json"
            }
            
            url = f"{self.api_url}/{payment_id}"
            
            response = await asyncio.to_thread(
                requests.get,
                url,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'unknown')
                logger.info(f"✅ Статус платежа {payment_id}: {status}")
                return status
            else:
                logger.error(f"❌ Ошибка получения статуса: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"❌ Ошибка: {str(e)}")
            return None
    
    def verify_webhook(self, request_body: str, signature: str) -> bool:
        """Проверить подпись вебхука"""
        
        try:
            expected_signature = base64.b64encode(
                (request_body + self.secret_key).encode()
            ).decode()
            
            return signature == expected_signature
        except Exception as e:
            logger.error(f"❌ Ошибка проверки подписи: {str(e)}")
            return False

# Глобальный экземпляр (НАСТРОЙТЕ КЛЮЧИ!)
# payment_handler = PaymentHandler(
#     shop_id="YOUR_SHOP_ID",
#     secret_key="YOUR_SECRET_KEY"
# )
