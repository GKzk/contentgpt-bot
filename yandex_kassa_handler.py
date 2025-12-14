# yandex_kassa_handler.py

import uuid
import requests
import hmac
import hashlib
from loguru import logger
from config import settings


class YandexKassaHandler:
    """Обработчик платежей ЮKassa"""

    API_URL = "https://api.yookassa.ru/v3"

    def __init__(self):
        self.shop_id = settings.YANDEX_KASSA_SHOP_ID
        self.secret_key = settings.YANDEX_KASSA_SECRET_KEY

    def create_payment(self, amount: float, description: str, order_id: str):
        if not self.shop_id or not self.secret_key:
            logger.error("❌ ЮKassa не настроена")
            return {"status": "error", "message": "ЮKassa не настроена"}

        payload = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": getattr(settings, 'PAYMENT_RETURN_URL', 'https://example.com'),

            },
            "capture": True,
            "description": description,
            "metadata": {"order_id": order_id},
        }

        headers = {
            "Content-Type": "application/json",
            "Idempotence-Key": str(uuid.uuid4()),
        }

        try:
            response = requests.post(
                f"{self.API_URL}/payments",
                json=payload,
                headers=headers,
                auth=(self.shop_id, self.secret_key),
                timeout=settings.REQUEST_TIMEOUT,
            )

            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"✅ Платёж создан: {data.get('id')}")
                return {
                    "status": "success",
                    "payment_id": data.get("id"),
                    "confirmation_url": (data.get("confirmation") or {}).get("confirmation_url", ""),
                    "amount": amount,
                }

            logger.error(f"❌ Ошибка создания платежа: {response.text}")
            return {"status": "error", "message": response.text}

        except Exception as e:
            logger.error(f"❌ Исключение при создании платежа: {e}")
            return {"status": "error", "message": str(e)}

    def get_payment_status(self, payment_id: str):
        if not self.shop_id or not self.secret_key:
            return {"status": "error", "message": "ЮKassa не настроена"}

        try:
            response = requests.get(
                f"{self.API_URL}/payments/{payment_id}",
                auth=(self.shop_id, self.secret_key),
                timeout=settings.REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "payment_status": data.get("status"),
                    "amount": (data.get("amount") or {}).get("value"),
                    "created_at": data.get("created_at"),
                    "test": data.get("test"),
                }

            logger.error(f"❌ Ошибка получения статуса: {response.text}")
            return {"status": "error", "message": response.text}

        except Exception as e:
            logger.error(f"❌ Исключение при получении статуса: {e}")
            return {"status": "error", "message": str(e)}

    def verify_webhook(self, event_id: str, signature: str):
        # Внимание: для v3 webhooks обычно проверяют “секрет вебхука”/заголовки по схеме,
        # которую вы реально настроили в ЛК, а не secret_key магазина.
        try:
            expected = hmac.new(
                self.secret_key.encode(),
                event_id.encode(),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки подписи: {e}")
            return False


kassa = YandexKassaHandler()
