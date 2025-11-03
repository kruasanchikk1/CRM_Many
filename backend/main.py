import os
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import json
import httpx
import base64

# Импорт сервисов
from backend.services.gdocs_service import GoogleDocsService

load_dotenv()

app = FastAPI(title="Voice2Action API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация сервисов
try:
    gdocs = GoogleDocsService()
    logger.info("✅ Google Docs сервис инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации Google Docs: {e}")
    gdocs = None


async def transcribe_yandex_speechkit(audio_data: bytes, filename: str) -> str:
    """Транскрипция через Yandex SpeechKit"""
    try:
        # Кодируем аудио в base64
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')

        # Определяем формат аудио
        if filename.endswith('.ogg'):
            audio_format = "OGG_OPUS"
        elif filename.endswith('.wav'):
            audio_format = "LINEAR16_PCM"
        elif filename.endswith('.mp3'):
            audio_format = "MP3"
        else:
            audio_format = "OGG_OPUS"  # по умолчанию

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
                headers={
                    "Authorization": f"Api-Key {os.getenv('YANDEX_API_KEY')}",
                },
                json={
                    "audio": {"data": audio_b64},
                    "config": {
                        "specification": {
                            "languageCode": "ru-RU",
                            "audioEncoding": audio_format,
                            "sampleRateHertz": 48000
                        }
                    }
                },
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('result', 'Текст не распознан')
            else:
                logger.error(f"Yandex SpeechKit error: {response.status_code} - {response.text}")
                return f"Ошибка распознавания: {response.status_code}"

    except Exception as e:
        logger.error(f"Yandex SpeechKit failed: {e}")
        return f"Ошибка сервиса: {str(e)}"


async def analyze_with_deepseek(transcript_text: str) -> dict:
    """Анализ транскрипта через DeepSeek API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": """Ты — ассистент для встреч. Извлеки из текста:
1. Краткое резюме (2-3 предложения)
2. Список задач в JSON формате:

Верни ТОЛЬКО JSON без каких-либо объяснений:

{
  "summary": "текст резюме",
  "tasks": [
    {
      "description": "текст задачи",
      "deadline": "YYYY-MM-DD или 'Не указан'", 
      "assignee": "имя или 'Не указан'",
      "priority": "High/Medium/Low",
      "action_type": "create_doc/send_email/create_task/call/message"
    }
  ]
}"""
                        },
                        {
                            "role": "user",
                            "content": f"Транскрипт встречи:\n\n{transcript_text}"
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                analysis_text = result['choices'][0]['message']['content']

                # Парсим JSON
                try:
                    return json.loads(analysis_text.strip())
                except:
                    # Если не JSON, возвращаем как есть
                    return {"summary": analysis_text, "tasks": []}
            else:
                logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                return {"summary": "Анализ не удался", "tasks": []}

    except Exception as e:
        logger.error(f"DeepSeek analysis failed: {e}")
        return {"summary": f"Ошибка анализа: {str(e)}", "tasks": []}


@app.get("/")
async def root():
    return {"message": "Voice2Action API v1.0", "status": "running"}


@app.get("/health")
async def health_check():
    """Проверка статуса сервисов"""
    return {
        "status": "running",
        "yandex_speechkit": "configured" if os.getenv("YANDEX_API_KEY") else "missing",
        "deepseek_ai": "configured" if os.getenv("DEEPSEEK_API_KEY") else "missing",
        "google_docs": "connected" if gdocs else "disconnected"
    }


@app.post("/api/process-audio")
async def process_audio(file: UploadFile = File(...)):
    """Обработка аудио: Yandex SpeechKit → DeepSeek AI → Google Docs"""

    if not gdocs:
        raise HTTPException(500, "Google Docs service not initialized")

    try:
        # 1. Валидация
        valid_types = ['audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'audio/mp3']
        if file.content_type and file.content_type not in valid_types:
            logger.warning(f"Unsupported content type: {file.content_type}")

        # 2. Чтение файла
        audio = await file.read()
        if len(audio) > 10 * 1024 * 1024:  # 10 МБ
            raise HTTPException(400, "File too large (max 10MB)")

        logger.info(f"Processing file: {file.filename}, size: {len(audio)} bytes")

        # 3. Транскрипция через Yandex SpeechKit
        transcript_text = await transcribe_yandex_speechkit(audio, file.filename)
        logger.info(f"Transcription completed: {len(transcript_text)} chars")

        # 4. AI анализ через DeepSeek
        analysis_result = await analyze_with_deepseek(transcript_text)
        logger.info(f"AI analysis completed: {len(analysis_result.get('tasks', []))} tasks found")

        # 5. Создание Google Docs
        doc_url = gdocs.create_doc(
            title=f"Анализ встречи – {file.filename}",
            content=f"# Резюме\n\n{analysis_result.get('summary', 'Не найдено')}\n\n# Полный транскрипт\n\n{transcript_text}"
        )
        logger.info(f"Google Doc created: {doc_url}")

        # 6. Создание Google Sheets с задачами
        tasks = analysis_result.get('tasks', [])
        sheet_url = None
        if tasks:
            sheet_url = gdocs.create_sheet(
                title=f"Задачи – {file.filename}",
                tasks=tasks
            )
            logger.info(f"Google Sheet created: {sheet_url}")

        # 7. Ответ
        return {
            "status": "success",
            "transcript": transcript_text,
            "analysis": analysis_result,
            "google_doc": doc_url,
            "google_sheet": sheet_url,
            "message": "Аудио успешно обработано: транскрипция + AI анализ"
        }

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise HTTPException(500, f"Processing failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)