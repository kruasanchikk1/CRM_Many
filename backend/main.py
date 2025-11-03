import os
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv
import json
import speech_recognition as sr
from pydub import AudioSegment
import io

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

# Инициализация клиентов С ЗАЩИТОЙ ОТ ОШИБОК
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info("✅ OpenAI клиент инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации OpenAI: {e}")
    client = None

try:
    gdocs = GoogleDocsService()
    logger.info("✅ Google Docs сервис инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации Google Docs: {e}")
    gdocs = None


def transcribe_audio_local(audio_data: bytes, filename: str) -> str:
    """Бесплатная транскрипция через Google Speech Recognition"""
    try:
        logger.info(f"Starting local transcription for: {filename}")

        # Конвертируем в WAV
        if filename.endswith('.ogg'):
            audio = AudioSegment.from_ogg(io.BytesIO(audio_data))
        elif filename.endswith('.mp3'):
            audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
        elif filename.endswith('.wav'):
            audio = AudioSegment.from_wav(io.BytesIO(audio_data))
        else:
            # Пробуем автоматическое определение формата
            audio = AudioSegment.from_file(io.BytesIO(audio_data))

        # Конвертируем в моно, 16kHz для лучшего распознавания
        audio = audio.set_channels(1).set_frame_rate(16000)

        wav_data = io.BytesIO()
        audio.export(wav_data, format='wav')
        wav_data.seek(0)

        # Транскрипция через Google Speech Recognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_data) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language='ru-RU')
            logger.info(f"Local transcription successful: {len(text)} chars")
            return text

    except sr.UnknownValueError:
        logger.error("Google Speech Recognition could not understand audio")
        return "Речь не распознана. Пожалуйста, попробуйте другой файл."
    except sr.RequestError as e:
        logger.error(f"Google Speech Recognition error: {e}")
        return f"Ошибка сервиса распознавания: {e}"
    except Exception as e:
        logger.error(f"Local transcription failed: {e}")
        return f"Ошибка обработки аудио: {str(e)}"

@app.get("/")
async def root():
    return {"message": "Voice2Action API v1.0", "status": "running"}

@app.get("/health")
async def health_check():
    """Проверка статуса сервисов"""
    return {
        "status": "running",
        "openai": "connected" if client else "disconnected",
        "google_docs": "connected" if gdocs else "disconnected"
    }


@app.post("/api/process-audio")
async def process_audio(file: UploadFile = File(...)):
    """Обработка аудио: локальная транскрипция → Google Docs"""

    # Проверка инициализации сервисов
    if not gdocs:
        raise HTTPException(500, "Google Docs service not initialized")

    try:
        # 1. Валидация
        valid_types = ['audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'audio/mp3']
        if file.content_type and file.content_type not in valid_types:
            logger.warning(f"Unsupported content type: {file.content_type}")

        # 2. Чтение файла
        audio = await file.read()
        if len(audio) > 10 * 1024 * 1024:  # 10 МБ максимум для бесплатной версии
            raise HTTPException(400, "File too large (max 10MB)")

        logger.info(f"Processing file: {file.filename}, size: {len(audio)} bytes")

        # 3. Локальная транскрипция (бесплатная)
        transcript_text = transcribe_audio_local(audio, file.filename)

        # 4. Создание Google Docs
        doc_url = gdocs.create_doc(
            title=f"Транскрипт – {file.filename}",
            content=f"# Транскрипт аудио\n\n{transcript_text}"
        )

        logger.info(f"Google Doc created: {doc_url}")

        # 5. Ответ
        return {
            "status": "success",
            "transcript": transcript_text,
            "google_doc": doc_url,
            "message": "Аудио успешно обработано и сохранено в Google Docs"
        }

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise HTTPException(500, f"Processing failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)