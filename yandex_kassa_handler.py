# yandex_kassa_handler.py - ОБРАБОТЧИК ЯНДЕКС.КАССА

import requests
import json
import hmac
import hashlib
from datetime import datetime
from loguru import logger
from config import settings

class YandexKassaHandler:
    """Обработчик платежей Яндекс.Касса"""
    
    BASE_URL = "https://api.yandex.checkout.com/v3"
    
    def __init__(self):
        self.shop_id = settings.YANDEX_KASSA_SHOP_ID
        self.secret_key = settings.YANDEX_KASSA_SECRET_KEY
    
    def create_payment(self, amount: float, description: str, order_id: str):
        """Создать платёж в Яндекс.Касса"""
        
        if not self.shop_id or not self.secret_key:
            logger.error("❌ Яндекс.Касса не настроена")
            return {'status': 'error', 'message': 'Яндекс.Касса не настроена'}
        
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
                "return_url": settings.PAYMENT_WEBHOOK_URL or "https://example.com"
            },
            "capture": True,
            "description": description,
            "metadata": {
                "order_id": order_id
            }
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/payments",
                json=payload,
                auth=(self.shop_id, self.secret_key),
                timeout=settings.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Платёж Яндекс.Касса создан: {data['id']}")
                return {
                    'status': 'success',
                    'payment_id': data['id'],
                    'confirmation_url': data.get('confirmation', {}).get('confirmation_url', ''),
                    'amount': amount
                }
            else:
                logger.error(f"❌ Ошибка создания платежа: {response.text}")
                return {'status': 'error', 'message': response.text}
        
        except Exception as e:
            logger.error(f"❌ Исключение при создании платежа: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def get_payment_status(self, payment_id: str):
        """Получить статус платежа"""
        
        if not self.shop_id or not self.secret_key:
            return {'status': 'error', 'message': 'Яндекс.Касса не настроена'}
        
        try:
            response = requests.get(
                f"{self.BASE_URL}/payments/{payment_id}",
                auth=(self.shop_id, self.secret_key),
                timeout=settings.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data['status']
                logger.info(f"✅ Статус платежа {payment_id}: {status}")
                return {
                    'status': 'success',
                    'payment_status': status,
                    'amount': data.get('amount', {}).get('value'),
                    'created_at': data.get('created_at')
                }
            else:
                logger.error(f"❌ Ошибка получения статуса: {response.text}")
                return {'status': 'error', 'message': response.text}
        
        except Exception as e:
            logger.error(f"❌ Исключение при получении статуса: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def verify_webhook(self, event_id: str, signature: str):
        """Проверить подпись webhook"""
        
        try:
            expected_signature = hmac.new(
                self.secret_key.encode(),
                event_id.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки подписи: {e}")
            return False

# Глобальный экземпляр
kassa = YandexKassaHandler()