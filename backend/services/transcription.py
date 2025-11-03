import os
import logging
from openai import OpenAI
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
logger = logging.getLogger(__name__)


def get_duration(file_path: str) -> float:
    """Получить длительность аудио в секундах"""
    audio = AudioSegment.from_file(file_path)
    return len(audio) / 1000.0


def split_audio(file_path: str, chunk_sec: int = 1800) -> list:
    """Разбить аудио на чанки по 30 минут"""
    audio = AudioSegment.from_file(file_path)
    duration_ms = len(audio)
    chunks = []
    
    for i in range(0, duration_ms, chunk_sec * 1000):
        chunk = audio[i:i + chunk_sec * 1000]
        chunk_path = f"/tmp/chunk_{os.getpid()}_{i}.mp3"
        chunk.export(chunk_path, format="mp3")
        chunks.append(chunk_path)
    
    return chunks


async def transcribe_audio(file_path: str) -> dict:
    """
    Транскрибация аудио через OpenAI Whisper
    
    Для файлов >30 мин автоматически разбивает на чанки
    """
    try:
        duration = get_duration(file_path)
        logger.info(f"Audio duration: {duration:.1f}s")
        
        # Если аудио >30 минут, разбиваем на чанки
        if duration > 1800:
            logger.info(f"Audio >30 min, splitting into chunks...")
            chunks = split_audio(file_path)
            full_text = ""
            segments = []
            offset = 0
            
            for idx, chunk_path in enumerate(chunks):
                logger.info(f"Transcribing chunk {idx + 1}/{len(chunks)}")
                
                try:
                    with open(chunk_path, "rb") as f:
                        result = openai_client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                            language="ru",
                            response_format="verbose_json",
                            temperature=0.2
                        )
                    
                    # Сдвигаем таймкоды
                    for seg in result.segments:
                        seg["start"] += offset
                        seg["end"] += offset
                        segments.append(seg)
                    
                    full_text += result.text + " "
                    offset += get_duration(chunk_path)
                
                finally:
                    # Удаляем временный чанк
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)
            
            return {
                "text": full_text.strip(),
                "segments": segments,
                "duration": duration,
                "language": "ru"
            }
        
        # Обычная транскрибация для файлов <30 минут
        else:
            with open(file_path, "rb") as f:
                result = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="ru",
                    response_format="verbose_json",
                    temperature=0.2
                )
            
            return {
                "text": result.text,
                "segments": result.segments if hasattr(result, 'segments') else [],
                "duration": duration,
                "language": result.language if hasattr(result, 'language') else "ru"
            }
    
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise Exception(f"Не удалось распознать аудио: {str(e)}")
