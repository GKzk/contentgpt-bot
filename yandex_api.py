# yandex_api.py - Интеграция с YandexGPT API
import requests
import asyncio
from typing import Optional
from config import settings
from loguru import logger

class YandexGPTHandler:
    """Обработчик запросов к YandexGPT API"""
    
    def __init__(self):
        self.api_key = settings.YANDEX_API_KEY
        self.folder_id = settings.YANDEX_FOLDER_ID
        
        # ПРАВИЛЬНЫЙ URL для YandexGPT API
        self.url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        
        self.model_name = "yandexgpt"
    
    async def generate_social_post(self, platform: str, topic: str, words: int = 150) -> Optional[str]:
        """Генерировать пост для социальной сети"""
        
        prompt = f"""Напиши привлекательный и вирусный пост для {platform} на тему: "{topic}".
        
Требования:
- Максимум {words} слов
- Используй релевантные эмодзи
- Добавь хэштеги в конце
- Будь креативным и эмоциональным
- Формат должен быть оптимален для {platform}

Ответ только пост, без дополнительного текста."""
        
        return await self._call_yandex_gpt(prompt)
    
    async def generate_ad_slogan(self, product: str, audience: str) -> Optional[str]:
        """Генерировать рекламный слоган"""
        
        prompt = f"""Создай 3-5 креативных рекламных слоганов для продукта: "{product}"
        
Целевая аудитория: {audience}

Требования:
- Слоганы должны быть запоминающимися
- Максимум 10 слов каждый
- Должны вызывать эмоции и желание покупки
- Используй силу слов и метафоры

Формат ответа:
1. Слоган 1
2. Слоган 2
3. Слоган 3"""
        
        return await self._call_yandex_gpt(prompt)
    
    async def generate_product_description(self, product_type: str, description: str, style: str = "продающий") -> Optional[str]:
        """Генерировать описание товара"""
        
        prompt = f"""Напиши {style} описание для {product_type}:

Исходная информация: {description}

Требования:
- Описание должно вызывать желание купить
- Подчеркни уникальные преимущества
- Используй убедительный язык
- Структурируй текст абзацами
- Добавь информацию о качестве
- Максимум 300 слов

Ответ только описание, без лишнего текста."""
        
        return await self._call_yandex_gpt(prompt)
    
    async def generate_content_ideas(self, topic: str, audience: str, count: int = 5) -> Optional[str]:
        """Генерировать идеи контента"""
        
        prompt = f"""Предложи {count} уникальных идей для контента на тему: "{topic}"
        
Целевая аудитория: {audience}

Требования:
- Идеи должны быть оригинальными и привлекательными
- Каждая идея - краткое описание (1-2 предложения)
- Укажи, для каких платформ подходит каждая идея
- Идеи должны быть легко реализуемыми

Формат ответа:
1. Идея 1 - [Платформы]
2. Идея 2 - [Платформы]
И т.д."""
        
        return await self._call_yandex_gpt(prompt)
    
    async def answer_faq(self, question: str, context: str = "") -> Optional[str]:
        """Ответить на часто задаваемый вопрос"""
        
        context_text = f"\nКонтекст: {context}" if context else ""
        
        prompt = f"""Напиши профессиональный и подробный ответ на следующий часто задаваемый вопрос:

Вопрос: "{question}"{context_text}

Требования:
- Ответ должен быть ясным и понятным
- Используй структурированный формат
- Упомяни практические примеры
- Если нужно, добавь список преимуществ
- Максимум 400 слов
- Будь дружелюбным и профессиональным"""
        
        return await self._call_yandex_gpt(prompt)
    
    async def _call_yandex_gpt(self, prompt: str, retries: int = 0) -> Optional[str]:
        """
        Внутренний метод для вызова YandexGPT API
        
        Args:
            prompt: Текст промпта
            retries: Текущее количество попыток
        
        Returns:
            Ответ от YandexGPT или None при ошибке
        """
        
        try:
            headers = {
                "Authorization": f"Api-Key {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "modelUri": f"gpt://{self.folder_id}/{self.model_name}/latest",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.7,
                    "maxTokens": "1000"
                },
                "messages": [
                    {
                        "role": "user",
                        "text": prompt
                    }
                ]
            }
            
            response = await asyncio.to_thread(
                requests.post,
                self.url,
                json=data,
                headers=headers,
                timeout=settings.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                
                try:
                    text = result['result']['alternatives'][0]['message']['text']
                    logger.info(f"✅ YandexGPT запрос успешен")
                    return text
                except (KeyError, IndexError) as e:
                    logger.error(f"❌ Ошибка при парсинге ответа: {str(e)}")
                    return None
            
            elif response.status_code == 401:
                logger.error("❌ Ошибка аутентификации. Проверьте API ключ и Folder ID")
                return None
            
            elif response.status_code == 403:
                logger.error("❌ Доступ запрещён. Проверьте права сервисного аккаунта")
                return None
            
            elif response.status_code == 404:
                logger.error(f"❌ Ошибка 404: неправильный URL API")
                logger.error(f"Текущий URL: {self.url}")
                return None
            
            elif response.status_code == 429:
                logger.warning(f"⚠️ Превышен лимит запросов. Попытка {retries + 1}/{settings.MAX_RETRIES}")
                if retries < settings.MAX_RETRIES:
                    await asyncio.sleep(2 ** retries)
                    return await self._call_yandex_gpt(prompt, retries + 1)
                else:
                    logger.error("❌ Не удалось получить ответ после нескольких попыток")
                    return None
            
            else:
                logger.error(f"❌ Ошибка YandexGPT API: статус {response.status_code}")
                logger.error(f"Ответ: {response.text}")
                return None
        
        except requests.exceptions.Timeout:
            logger.error(f"❌ Таймаут при запросе к YandexGPT (>{settings.REQUEST_TIMEOUT}с)")
            return None
        
        except requests.exceptions.ConnectionError:
            logger.error("❌ Ошибка подключения к YandexGPT API")
            return None
        
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {str(e)}")
            return None

# Глобальный экземпляр
yandex_gpt_handler = YandexGPTHandler()
