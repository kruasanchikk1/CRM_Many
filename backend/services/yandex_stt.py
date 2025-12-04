import os
import logging
import httpx

logger = logging.getLogger(__name__)

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")


async def transcribe_audio(audio_path: str) -> dict:
    """Транскрибация аудио через Yandex SpeechKit REST API"""
    
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        raise ValueError("YANDEX_API_KEY или YANDEX_FOLDER_ID не найдены")
    
    try:
        logger.info(f"Начало транскрибации: {audio_path}")
        
        # Чтение аудио файла
        with open(audio_path, 'rb') as audio_file:
            audio_data = audio_file.read()
        
        # Определяем формат аудио по расширению
        file_ext = audio_path.lower().split('.')[-1]
        
        if file_ext == 'mp3' or file_ext == 'mpeg':
            content_type = 'audio/mpeg'
        elif file_ext == 'wav':
            content_type = 'audio/wav'
        elif file_ext == 'ogg':
            content_type = 'audio/ogg'
        elif file_ext == 'm4a' or file_ext == 'mp4':
            content_type = 'audio/mp4'
        else:
            content_type = 'audio/mpeg'  # Fallback
        
        # Подготовка заголовков
        headers = {
            'Authorization': f'Api-Key {YANDEX_API_KEY}',
            'Content-Type': content_type
        }
        
        params = {
            'folderId': YANDEX_FOLDER_ID,
            'lang': 'ru-RU'
        }
        
        # Отправка запроса к SpeechKit (async)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize',
                headers=headers,
                params=params,
                content=audio_data
            )
            
            response.raise_for_status()
            result = response.json()
            text = result.get("result", "")

            logger.info(f"Распознанный текст: '{text}'")  # ← ВОТ ЭТА СТРОКА!

            if not text:
                logger.warning("Пустой транскрипт от Yandex SpeechKit")
                raise ValueError("Не удалось распознать речь")
            
            logger.info(f"Транскрибация завершена: {len(text)} символов")
            
            return {
                "text": text,
                "language": "ru",
                "duration": 0  # Можно вычислить из файла при необходимости
            }
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP ошибка Yandex SpeechKit: {e.response.status_code} - {e.response.text}")
        raise ValueError(f"Yandex SpeechKit error: {e.response.status_code}")
    
    except Exception as e:
        logger.error(f"Ошибка транскрибации: {e}")
        raise