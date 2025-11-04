import os
import uuid
import logging
import tempfile
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Импорт Yandex сервисов (ИСПРАВЛЕНО!)
try:
    from services.yandex_stt import transcribe_audio
    from services.yandex_gpt import analyze_transcript
    from services.gdocs_service import GoogleDocsService
except ImportError:
    # Для локальной разработки
    from backend.services.yandex_stt import transcribe_audio
    from backend.services.yandex_gpt import analyze_transcript
    from backend.services.gdocs_service import GoogleDocsService

load_dotenv()

app = FastAPI(title="Voice2Action API v2.0")

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

# Google Docs сервис (инициализируется при старте)
try:
    gdocs = GoogleDocsService()
except Exception as e:
    logger.error(f"Failed to initialize Google Docs: {e}")
    gdocs = None

# In-memory хранилище задач (в продакшене использовать Redis/PostgreSQL)
jobs = {}


class ExportRequest(BaseModel):
    job_id: str
    exports: List[str]  # ["google_docs", "google_sheets"]


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    complete: bool
    error: Optional[str] = None
    results: Optional[dict] = None


@app.get("/")
async def root():
    return {
        "message": "Voice2Action API v2.0",
        "status": "running",
        "engine": "Yandex SpeechKit + YandexGPT",
        "docs": "/docs"
    }


@app.post("/api/process-audio")
async def process_audio(
        audio: UploadFile = File(...),
        background_tasks: BackgroundTasks = None
):
    """
    Загрузка аудио и запуск обработки

    Pipeline:
    1. Yandex SpeechKit (транскрибация)
    2. YandexGPT (анализ и извлечение задач)
    3. Google Docs/Sheets (опционально через /api/export)
    """

    try:
        # 1. Валидация формата
        valid_types = [
            'audio/mpeg', 'audio/ogg', 'audio/wav',
            'audio/mp4', 'audio/x-m4a', 'audio/mp3'
        ]
        if audio.content_type and audio.content_type not in valid_types:
            logger.warning(f"Unsupported content type: {audio.content_type}")

        # 2. Валидация размера (25MB)
        content = await audio.read()
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(400, "File too large (max 25MB)")

        logger.info(f"Processing file: {audio.filename}, size: {len(content)} bytes")

        # 3. Генерация job_id
        job_id = str(uuid.uuid4())
        file_path = f"/tmp/{job_id}_{audio.filename}"

        # 4. Сохранение файла
        with open(file_path, "wb") as f:
            f.write(content)

        # 5. Инициализация job
        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "complete": False,
            "error": None,
            "results": None,
            "file_path": file_path,
            "filename": audio.filename
        }

        # 6. Запуск фоновой обработки
        background_tasks.add_task(process_pipeline, job_id, file_path)

        logger.info(f"Job {job_id} created for file {audio.filename}")
        return {
            "job_id": job_id,
            "message": "Processing started",
            "status_url": f"/api/status/{job_id}"
        }

    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(500, f"Failed to process audio: {str(e)}")


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """Проверка статуса обработки"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[job_id].copy()
    # Убираем временные данные из ответа
    job.pop("file_path", None)

    return job


@app.post("/api/export")
async def export_results(request: ExportRequest):
    """
    Экспорт результатов в Google Docs/Sheets

    Exports:
    - google_docs: Google Document с резюме и транскриптом
    - google_sheets: Google Spreadsheet с задачами
    """

    if request.job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[request.job_id]

    if not job["complete"]:
        raise HTTPException(400, "Job not completed yet")

    if job["error"]:
        raise HTTPException(400, f"Job failed: {job['error']}")

    if not gdocs:
        raise HTTPException(500, "Google Docs service not initialized")

    results = job["results"]
    exports = {}

    try:
        # Google Docs экспорт
        if "google_docs" in request.exports:
            doc_content = f"""# Резюме встречи

{results['summary']}

## Ключевые моменты

{chr(10).join(f"- {point}" for point in results.get('key_points', []))}

## Принятые решения

{chr(10).join(f"- {decision}" for decision in results.get('decisions', []))}

## Полный транскрипт

{results['transcript']}
"""

            doc_url = gdocs.create_doc(
                title=f"Voice2Action – {job['filename']}",
                content=doc_content
            )

            exports["google_docs"] = {
                "status": "success",
                "doc_url": doc_url
            }
            logger.info(f"Google Doc created for job {request.job_id}")

        # Google Sheets экспорт
        if "google_sheets" in request.exports:
            tasks = results.get('tasks', [])
            if tasks:
                sheet_url = gdocs.create_sheet(
                    title=f"Voice2Action Tasks – {job['filename']}",
                    tasks=tasks
                )
                exports["google_sheets"] = {
                    "status": "success",
                    "sheet_url": sheet_url
                }
                logger.info(f"Google Sheet created for job {request.job_id}")
            else:
                exports["google_sheets"] = {
                    "status": "skipped",
                    "reason": "No tasks found"
                }

        return {"job_id": request.job_id, "exports": exports}

    except Exception as e:
        logger.error(f"Export failed for job {request.job_id}: {e}")
        raise HTTPException(500, f"Export failed: {str(e)}")


async def process_pipeline(job_id: str, file_path: str):
    """
    Основной pipeline обработки аудио

    1. Транскрибация через Yandex SpeechKit
    2. Анализ через YandexGPT
    3. Сохранение результатов
    """
    try:
        # Шаг 1: Транскрибация
        jobs[job_id].update({
            "status": "Транскрибация аудио (Yandex SpeechKit)...",
            "progress": 20
        })
        logger.info(f"Job {job_id}: Starting transcription")

        transcript_data = await transcribe_audio(file_path)
        transcript = transcript_data["text"]

        if not transcript or len(transcript) < 10:
            raise ValueError("Транскрипт пустой или слишком короткий")

        logger.info(f"Job {job_id}: Transcription completed ({len(transcript)} chars)")

        # Шаг 2: AI анализ
        jobs[job_id].update({
            "status": "Анализ текста (YandexGPT)...",
            "progress": 50
        })
        logger.info(f"Job {job_id}: Starting analysis")

        analysis = await analyze_transcript(transcript)

        logger.info(f"Job {job_id}: Analysis completed")

        # Шаг 3: Финализация
        jobs[job_id].update({
            "status": "Готово",
            "progress": 100,
            "complete": True,
            "results": {
                "summary": analysis.get('summary', 'Резюме не найдено'),
                "tasks": analysis.get('tasks', []),
                "key_points": analysis.get('key_points', []),
                "decisions": analysis.get('decisions', []),
                "transcript": transcript,
                "duration_seconds": transcript_data.get("duration", 0)
            }
        })

        logger.info(f"Job {job_id}: Completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        jobs[job_id].update({
            "status": "Ошибка",
            "error": str(e),
            "complete": True,
            "progress": 0
        })

    finally:
        # Удаление временного файла
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Job {job_id}: Temporary file removed")
        except Exception as e:
            logger.error(f"Failed to remove temp file: {e}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Проверка работоспособности API"""
    return {
        "status": "healthy",
        "yandex_api": os.getenv("YANDEX_API_KEY") is not None,
        "google_docs": gdocs is not None,
        "active_jobs": len([j for j in jobs.values() if not j["complete"]])
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)