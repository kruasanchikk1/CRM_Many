# main.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
import os
import tempfile
import uuid
import asyncio
import logging
import sqlite3
from typing import Optional, List, Dict
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ⚠️ КРИТИЧНО: Загрузка переменных окружения
load_dotenv()

# Импорт базы данных
try:
    from database import db
except ImportError:
    print("⚠️  database.py не найден. Создай его в папке backend/")
    raise

# Импорт Yandex сервисов
try:
    from services.yandex_stt import transcribe_audio
    from services.yandex_gpt import analyze_transcript
    from services.gdocs_service import add_to_google_docs
    print("✅ Импорт сервисов успешен")
except ImportError as e:
    print(f"⚠️  Ошибка импорта сервисов: {e}")
    print("📁 Проверь наличие папки services/ и файлов:")
    print("   - services/yandex_stt.py")
    print("   - services/yandex_gpt.py")
    print("   - services/gdocs_service.py")
    raise
# Инициализация приложения
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

# In-memory хранилище задач
jobs: Dict[str, Dict] = {}


# ========== PYDANTIC МОДЕЛИ ==========

class ExportRequest(BaseModel):
    job_id: str
    exports: List[str]


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    complete: bool
    error: Optional[str] = None
    results: Optional[dict] = None


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

async def process_pipeline(job_id: str, file_path: str, original_filename: str):
    """Полный пайплайн обработки"""
    try:
        # Сохраняем в БД
        db.create_job(job_id, original_filename)

        # 1. Транскрипция
        logger.info(f"Job {job_id}: Starting transcription")
        transcript_data = await transcribe_audio(file_path)
        transcript_text = transcript_data["text"]

        # Сохраняем транскрипт
        db.update_transcript(job_id, transcript_text)
        jobs[job_id]["transcript"] = transcript_text
        jobs[job_id]["transcript_chars"] = len(transcript_text)
        jobs[job_id]["progress"] = 50

        logger.info(f"Job {job_id}: Transcription completed ({len(transcript_text)} chars)")

        # 2. Анализ YandexGPT
        logger.info(f"Job {job_id}: Starting analysis")
        analysis_result = await analyze_transcript(transcript_text)

        # Сохраняем анализ
        db.save_analysis(job_id, analysis_result)
        jobs[job_id]["analysis"] = analysis_result
        jobs[job_id]["results"] = {
            "transcript": transcript_text,
            "summary": analysis_result.get("summary", ""),
            "tasks": analysis_result.get("tasks", []),
            "key_points": analysis_result.get("key_points", []),
            "decisions": analysis_result.get("decisions", [])
        }
        jobs[job_id]["progress"] = 75

        # 3. Сохранение в Google Docs
        logger.info(f"Job {job_id}: Saving to Google Docs")
        await add_to_google_docs(transcript_text, analysis_result)

        # Финальный статус
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["complete"] = True
        jobs[job_id]["completed_at"] = datetime.now().isoformat()

        logger.info(f"✅ Job {job_id}: Pipeline completed")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["complete"] = True

        # Обновляем статус в БД
        conn = sqlite3.connect("voice2action.db")
        c = conn.cursor()
        c.execute('''UPDATE jobs SET status = ? WHERE id = ?''',
                  ("failed", job_id))
        conn.commit()
        conn.close()


# ========== API ЭНДПОИНТЫ ==========

@app.get("/")
async def root():
    return {
        "message": "Voice2Action API v2.0",
        "status": "running",
        "engine": "Yandex SpeechKit + YandexGPT",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    try:
        # Проверяем подключение к БД
        conn = sqlite3.connect("voice2action.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM jobs")
        db_count = c.fetchone()[0]
        conn.close()

        # Проверяем Yandex ключи
        YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
        YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "fastapi": True,
                "database": True,
                "yandex_api": bool(YANDEX_API_KEY and len(YANDEX_API_KEY) > 10),
                "yandex_folder": bool(YANDEX_FOLDER_ID and len(YANDEX_FOLDER_ID) > 5),
                "google_docs": True
            },
            "statistics": {
                "total_jobs": db_count,
                "active_jobs": len([j for j in jobs.values() if j.get("status") == "processing"]),
                "completed_jobs": len([j for j in jobs.values() if j.get("status") == "completed"])
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "services": {
                "fastapi": True,
                "database": False,
                "yandex_api": False,
                "google_docs": False
            }
        }


@app.get("/api/jobs", response_model=List[dict])
async def list_jobs(limit: int = 50, offset: int = 0):
    """Список всех задач"""
    jobs_list = db.get_all_jobs(limit=limit)
    return [
        {
            "job_id": job["id"],
            "filename": job["filename"],
            "status": job["status"],
            "created_at": job["created_at"],
            "completed_at": job["completed_at"],
            "has_analysis": job.get("has_analysis", False)
        }
        for job in jobs_list[offset:offset + limit]
    ]


@app.get("/api/jobs/{job_id}", response_model=dict)
async def get_job_details(job_id: str):
    """Полная информация о задаче"""
    job_data = db.get_job(job_id)

    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    # Форматируем ответ
    response = {
        "job_id": job_data["id"],
        "filename": job_data["filename"],
        "status": job_data["status"],
        "created_at": job_data["created_at"],
        "completed_at": job_data["completed_at"],
        "transcript": {
            "text": job_data.get("transcript_text", ""),
            "characters": job_data.get("transcript_chars", 0)
        }
    }

    # Добавляем анализ если есть
    if job_data.get("analysis"):
        response["analysis"] = job_data["analysis"]

    # Добавляем извлечённые задачи
    if job_data.get("extracted_tasks"):
        response["extracted_tasks"] = job_data["extracted_tasks"]

    return response


@app.get("/api/jobs/{job_id}/transcript")
async def get_job_transcript(job_id: str):
    """Получить только транскрипт"""
    job_data = db.get_job(job_id)

    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job_id,
        "transcript": job_data.get("transcript_text", ""),
        "characters": job_data.get("transcript_chars", 0)
    }


@app.get("/api/jobs/{job_id}/analysis")
async def get_job_analysis(job_id: str):
    """Получить только анализ"""
    job_data = db.get_job(job_id)

    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job_data.get("analysis"):
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {
        "job_id": job_id,
        "analysis": job_data["analysis"]
    }


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Удалить задачу"""
    if db.delete_job(job_id):
        # Также удаляем из памяти
        if job_id in jobs:
            del jobs[job_id]
        return {"message": f"Job {job_id} deleted"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/stats")
async def get_statistics():
    """Получить статистику"""
    stats = db.get_statistics()
    return {
        "statistics": stats,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/search")
async def search_transcripts(query: str, limit: int = 20):
    """Поиск по транскриптам"""
    try:
        conn = sqlite3.connect("voice2action.db")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('''SELECT id, filename, transcript_text, created_at 
                    FROM jobs 
                    WHERE transcript_text LIKE ? 
                    AND transcript_text IS NOT NULL
                    ORDER BY created_at DESC 
                    LIMIT ?''',
                  (f"%{query}%", limit))

        results = []
        for row in c.fetchall():
            results.append({
                "job_id": row["id"],
                "filename": row["filename"],
                "snippet": row["transcript_text"][:200] + "..." if len(row["transcript_text"]) > 200 else row[
                    "transcript_text"],
                "created_at": row["created_at"]
            })

        conn.close()
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.post("/api/process-audio")
async def process_audio(audio: UploadFile = File(...)):
    """Загрузить аудио и запустить обработку"""
    try:
        # Создаём уникальный ID
        job_id = str(uuid.uuid4())

        # Сохраняем файл
        temp_dir = tempfile.gettempdir()
        safe_filename = f"{job_id}_{audio.filename.replace(' ', '_')}"
        file_path = os.path.join(temp_dir, safe_filename)

        with open(file_path, "wb") as f:
            content = await audio.read()
            f.write(content)

        # Создаём запись в памяти
        jobs[job_id] = {
            "id": job_id,
            "filename": audio.filename,
            "status": "processing",
            "progress": 0,
            "complete": False,
            "created_at": datetime.now().isoformat(),
            "file_path": file_path
        }

        # Запускаем обработку в фоне
        asyncio.create_task(process_pipeline(job_id, file_path, audio.filename))

        # Возвращаем улучшенный ответ
        return {
            "job_id": job_id,
            "message": "Processing started",
            "status_url": f"/api/jobs/{job_id}",
            "transcript_url": f"/api/jobs/{job_id}/transcript",
            "analysis_url": f"/api/jobs/{job_id}/analysis",
            "monitor_url": f"/api/status/{job_id}",
            "created_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """Проверка статуса обработки"""
    if job_id not in jobs:
        # Проверяем в БД
        job_data = db.get_job(job_id)
        if job_data:
            return {
                "job_id": job_id,
                "status": job_data["status"],
                "progress": 100 if job_data["status"] in ["completed", "failed"] else 0,
                "complete": job_data["status"] in ["completed", "failed"],
                "filename": job_data["filename"],
                "created_at": job_data["created_at"],
                "completed_at": job_data.get("completed_at")
            }
        raise HTTPException(404, "Job not found")

    job = jobs[job_id].copy()
    job.pop("file_path", None)
    return job


@app.post("/api/export")
async def export_results(request: ExportRequest):
    """Экспорт результатов в Google Docs/Sheets"""

    if request.job_id not in jobs:
        raise HTTPException(404, "Job not found")

    job = jobs[request.job_id]

    if not job.get("complete", False):
        raise HTTPException(400, "Job not completed yet")

    if job.get("error"):
        raise HTTPException(400, f"Job failed: {job['error']}")

    if not job.get("results"):
        raise HTTPException(400, "No results to export")

    exports = {}

    try:
        # Google Docs экспорт (через существующую функцию)
        if "google_docs" in request.exports:
            # Уже сделано в process_pipeline через add_to_google_docs
            exports["google_docs"] = {
                "status": "already_exported",
                "message": "Already exported during processing"
            }
            logger.info(f"Google Docs export noted for job {request.job_id}")

        # Дополнительный экспорт можно добавить здесь

        return {"job_id": request.job_id, "exports": exports}

    except Exception as e:
        logger.error(f"Export failed for job {request.job_id}: {e}")
        raise HTTPException(500, f"Export failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)