import os
import json
import logging
import httpx

logger = logging.getLogger(__name__)

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")


async def analyze_transcript(transcript: str) -> dict:
    """Анализ транскрипта через YandexGPT"""

    if not YANDEX_API_KEY or not FOLDER_ID:
        raise ValueError("YANDEX_API_KEY или YANDEX_FOLDER_ID не найдены в .env")

    try:
        logger.info(f"Начало анализа транскрипта: {len(transcript)} символов")

        # Промпт для анализа
        system_prompt = """Ты — ассистент для встреч. Проанализируй транскрипт и создай JSON:

{
  "summary": "Краткое резюме встречи (2-3 предложения)",
  "tasks": [
    {
      "description": "Описание задачи",
      "deadline": "YYYY-MM-DD или 'Не указан'",
      "assignee": "Имя или 'Не указан'",
      "priority": "High/Medium/Low"
    }
  ],
  "key_points": ["Ключевая точка 1", "Ключевая точка 2"],
  "decisions": ["Решение 1", "Решение 2"]
}

Используй ТОЛЬКО информацию из транскрипта."""

        # API запрос к YandexGPT
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

        headers = {
            "Authorization": f"Api-Key {YANDEX_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": 2000
            },
            "messages": [
                {
                    "role": "system",
                    "text": system_prompt
                },
                {
                    "role": "user",
                    "text": f"Транскрипт встречи:\n\n{transcript}"
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()

            result = response.json()
            gpt_text = result["result"]["alternatives"][0]["message"]["text"]

            logger.info(f"Анализ завершён: {len(gpt_text)} символов")

            # Парсинг JSON из ответа
            try:
                # Убираем markdown блоки
                clean_text = gpt_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]

                analysis = json.loads(clean_text.strip())
                return analysis

            except json.JSONDecodeError:
                logger.warning("Не удалось распарсить JSON, возвращаем текст")
                return {
                    "summary": gpt_text[:500],
                    "tasks": [],
                    "key_points": [],
                    "decisions": []
                }

    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        raise