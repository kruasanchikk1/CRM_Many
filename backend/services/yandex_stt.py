import os
import requests
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_path: str) -> Dict[str, Any]:
    """
    Транскрибация аудио через Yandex SpeechKit REST API
    """
    try:
        # Чтение аудио файла
        with open(audio_path, 'rb') as audio_file:
            audio_data = audio_file.read()

        # Определяем формат аудио по расширению
        file_ext = audio_path.lower().split('.')[-1]
        content_type = f"audio/{file_ext}"

        if file_ext == 'mp3':
            content_type = 'audio/mpeg'
        elif file_ext == 'wav':
            content_type = 'audio/wav'
        elif file_ext == 'ogg':
            content_type = 'audio/ogg'

        # Подготовка заголовков
        headers = {
            'Authorization': f'Api-Key {os.getenv("YANDEX_API_KEY")}',
            'Content-Type': content_type
        }

        params = {
            'folderId': os.getenv('YANDEX_FOLDER_ID'),
            'lang': 'ru-RU'
        }

        # Отправка запроса к SpeechKit
        response = requests.post(
            'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize',
            headers=headers,
            params=params,
            data=audio_data
        )

        if response.status_code == 200:
            result = response.json()
            text = result.get("result", "")

            logger.info(f"Transcription successful: {len(text)} chars")

            return {
                "text": text,
                "duration": 0  # Можно вычислить из файла при необходимости
            }
        else:
            logger.error(f"SpeechKit error: {response.status_code} - {response.text}")
            raise Exception(f"SpeechKit API error: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise
