# backend/services/yandex_stt.py
import os
import logging
import grpc
import sys
from pydub import AudioSegment
from yandex.cloud.ai.stt.v3 import stt_pb2, stt_service_pb2_grpc

# Настройка ffmpeg на Linux (Render)
if sys.platform.startswith("linux"):
    AudioSegment.ffmpeg = "./bin/ffmpeg"
    # AudioSegment.ffprobe = "./bin/ffprobe"  # если добавишь

logger = logging.getLogger(__name__)
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")

def convert_to_wav_16k(input_path: str) -> str:
    """Конвертирует любой аудио в WAV 16kHz mono"""
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    wav_path = input_path + ".wav"
    audio.export(wav_path, format="wav")
    return wav_path

async def transcribe_audio(audio_path: str) -> dict:
    if not YANDEX_API_KEY:
        raise ValueError("YANDEX_API_KEY не найден")

    channel = None
    wav_path = None

    try:
        logger.info(f"Конвертация аудио: {audio_path}")
        wav_path = convert_to_wav_16k(audio_path)

        with open(wav_path, "rb") as f:
            audio_data = f.read()

        if len(audio_data) > 1_000_000:
            raise ValueError("Аудио слишком длинное (>1МБ). Максимум ~60 секунд.")

        channel = grpc.aio.secure_channel('stt.api.cloud.yandex.net:443')
        stub = stt_service_pb2_grpc.RecognizerStub(channel)
        metadata = [('authorization', f'Api-Key {YANDEX_API_KEY}')]

        request = stt_pb2.RecognizeRequest(
            config=stt_pb2.RecognitionConfig(
                specification=stt_pb2.RecognitionSpec(
                    language_code='ru-RU',
                    model='general',
                    audio_encoding=stt_pb2.RecognitionSpec.LINEAR16_PCM,
                    sample_rate_hertz=16000,
                )
            ),
            audio=stt_pb2.AudioChunk(content=audio_data)
        )

        response = await stub.Recognize(request, metadata=metadata)

        transcript = " ".join([
            alt.text for chunk in response.chunks
            for alt in chunk.alternatives
        ]).strip()

        logger.info(f"Транскрибация завершена: {len(transcript)} символов")
        return {"text": transcript, "language": "ru"}

    except Exception as e:
        logger.error(f"Ошибка STT: {e}")
        raise

    finally:
        # Удаление временного файла
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить {wav_path}: {e}")

        # Закрытие gRPC
        if channel:
            try:
                await channel.close()
            except Exception as e:
                logger.warning(f"Ошибка закрытия gRPC: {e}")