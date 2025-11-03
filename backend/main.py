import os
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv
import json

# Импорт сервисов
from backend.services.gdocs_service import GoogleDocsService

load_dotenv()

app = FastAPI(title="Voice2Action API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене замени на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gdocs = GoogleDocsService()


@app.get("/")
async def root():
    return {"message": "Voice2Action API v1.0", "status": "running"}


@app.post("/api/process-audio")
async def process_audio(file: UploadFile = File(...)):
    """Обработка аудио: транскрипция → анализ → Google Docs"""

    try:
        # 1. Валидация
        valid_types = ['audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'audio/mp3']
        if file.content_type and file.content_type not in valid_types:
            logger.warning(f"Unsupported content type: {file.content_type}")

        # 2. Чтение файла
        audio = await file.read()
        if len(audio) > 25 * 1024 * 1024:  # 25 МБ
            raise HTTPException(400, "File too large (max 25MB)")

        logger.info(f"Processing file: {file.filename}, size: {len(audio)} bytes")

        # 3. Транскрибация (Whisper)
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=(file.filename, audio, file.content_type or "audio/mpeg")
        )

        logger.info(f"Transcription completed: {len(transcript.text)} chars")

        # 4. Анализ (GPT)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """Ты — ассистент для встреч. Создай:
1. Краткий summary (2-3 предложения)
2. Список задач в JSON формате:

{
  "summary": "Краткое описание встречи",
  "tasks": [
    {
      "description": "Описание задачи",
      "deadline": "YYYY-MM-DD или 'Не указан'",
      "assignee": "Имя или 'Не указан'",
      "priority": "High/Medium/Low"
    }
  ]
}

Используй ТОЛЬКО информацию из транскрипта."""
                },
                {"role": "user", "content": f"Транскрипт встречи:\n\n{transcript.text}"}
            ],
            temperature=0.3
        )

        analysis_text = response.choices[0].message.content
        logger.info(f"Analysis completed: {len(analysis_text)} chars")

        # 5. Парсинг JSON
        try:
            # Убираем markdown блоки, если есть
            clean_text = analysis_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            analysis_json = json.loads(clean_text.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}, using fallback")
            analysis_json = {
                "summary": analysis_text[:500],
                "tasks": []
            }

        # 6. Создание Google Docs
        doc_url = gdocs.create_doc(
            title=f"Voice2Action Summary – {file.filename}",
            content=f"# Резюме встречи\n\n{analysis_json.get('summary', 'Не найдено')}\n\n# Полный транскрипт\n\n{transcript.text}"
        )

        logger.info(f"Google Doc created: {doc_url}")

        # 7. Создание Google Sheet
        tasks = analysis_json.get('tasks', [])
        if tasks:
            sheet_url = gdocs.create_sheet(
                title=f"Voice2Action Tasks – {file.filename}",
                tasks=tasks
            )
            logger.info(f"Google Sheet created: {sheet_url}")
        else:
            sheet_url = None
            logger.warning("No tasks found")

        # 8. Ответ
        return {
            "status": "success",
            "transcript": transcript.text,
            "summary": analysis_json.get('summary', 'Не найдено'),
            "tasks": tasks,
            "google_doc": doc_url,
            "google_sheet": sheet_url,
            "analysis": analysis_text  # Для отладки
        }

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise HTTPException(500, f"Processing failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)