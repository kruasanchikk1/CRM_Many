"""
Voice2Action Telegram Bot v2.2 (python-telegram-bot v21+)
✅ Полная совместимость Python 3.14
✅ Yandex SpeechKit + YandexGPT + Google Docs
✅ Без Updater ошибок!
"""

import os
import asyncio
import logging
from pathlib import Path
import httpx
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

# Конфигурация
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN не найден в .env!")
    exit(1)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальное приложение для send_message
application = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    text = (
        "🎙️ *Voice2Action Bot*\n\n"
        "🚀 *Что делает:*\n"
        "• Транскрипция → Yandex SpeechKit\n"
        "• Анализ → YandexGPT\n"
        "• Резюме + задачи + Google Docs\n\n"
        "*Отправь голосовое или аудио (≤25MB)!*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help"""
    text = (
        "📖 *Инструкция:*\n\n"
        f"1️⃣ Голосовое / аудио (MP3/OGG/WAV ≤25MB)\n"
        "2️⃣ Выбери тип анализа\n"
        "3️⃣ Результат за 30-120 сек\n\n"
        f"*Backend:* {API_BASE_URL}\n"
        f"*Swagger:* {API_BASE_URL}/docs"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка голосовых и аудио файлов"""
    message = update.message

    try:
        # Получаем файл
        if message.voice:
            file = await message.voice.get_file()
            filename = f"voice_{message.message_id}.ogg"
        elif message.audio:
            file = await message.audio.get_file()
            ext = Path(file.file_path or "").suffix or ".mp3"
            filename = f"audio_{message.message_id}{ext}"
        else:
            await message.reply_text("❌ Отправь голосовое или аудио файл!")
            return

        # Сохраняем локально
        file_path = Path(filename)
        await file.download_to_drive(str(file_path))
        context.user_data["file_path"] = str(file_path)

        # Кнопки анализа
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✨ Авто", callback_data="auto"),
                InlineKeyboardButton("📋 Встреча", callback_data="meeting")
            ],
            [
                InlineKeyboardButton("💼 Продажи", callback_data="sales"),
                InlineKeyboardButton("👤 Интервью", callback_data="interview")
            ],
            [InlineKeyboardButton("📝 Лекция", callback_data="lecture")]
        ])

        # Размер файла
        size_mb = file_path.stat().st_size / (1024 * 1024)
        await message.reply_text(
            f"✅ *Файл загружен!*\n\n"
            f"📁 `{filename}` ({size_mb:.1f} МБ)\n\n"
            "🎯 *Выбери тип анализа:*",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.error(f"File download error: {e}")
        await message.reply_text("❌ Ошибка загрузки файла. Попробуй другой!")


async def analysis_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора типа анализа"""
    query = update.callback_query
    await query.answer()

    analysis_type = query.data
    file_path = context.user_data.get("file_path")

    if not file_path or not Path(file_path).exists():
        await query.edit_message_text("❌ Файл потерян. Отправь заново!")
        return

    # Обновляем сообщение
    analysis_names = {
        "auto": "Авто (YandexGPT выберет)",
        "meeting": "Встреча",
        "sales": "Продажи",
        "interview": "Интервью",
        "lecture": "Лекция"
    }
    name = analysis_names.get(analysis_type, analysis_type.title())

    await query.edit_message_text(
        f"🚀 *{name} анализ запущен...*\n\n"
        "⏳ Yandex SpeechKit → YandexGPT → результаты\n"
        "(30-120 секунд)"
    )

    try:
        # 1. Загрузка в backend
        job_id = await upload_audio(file_path, analysis_type)
        await query.message.reply_text(
            f"✅ *Job создан!*\n\n"
            f"🆔 `{job_id}`\n"
            f"⏳ Отслеживаю статус..."
        )

        # 2. Polling результата
        job = await poll_job(job_id)

        # 3. Показываем результат
        await show_results(job, query.message.chat_id)

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        await query.message.reply_text(f"❌ *Ошибка:* {str(e)}")
    finally:
        # Очистка
        cleanup_file(file_path)
        if "file_path" in context.user_data:
            del context.user_data["file_path"]


async def upload_audio(file_path: str, analysis_type: str) -> str:
    """Отправка аудио в FastAPI backend"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(file_path, "rb") as audio_file:
            files = {"audio": (Path(file_path).name, audio_file)}
            data = {"analysis_type": analysis_type}
            response = await client.post(
                f"{API_BASE_URL}/api/process-audio",
                files=files,
                data=data
            )
        response.raise_for_status()
        return response.json()["job_id"]


async def poll_job(job_id: str) -> dict:
    """Опрос статуса job (максимум 3 минуты)"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(90):
            try:
                response = await client.get(f"{API_BASE_URL}/api/jobs/{job_id}")
                if response.status_code != 200:
                    await asyncio.sleep(2)
                    continue

                job = response.json()
                status = job.get("status", "processing")

                if status == "completed":
                    return job
                if status == "failed":
                    raise RuntimeError(job.get("error", "Unknown backend error"))

            except Exception as e:
                logger.warning(f"Poll attempt {attempt}: {e}")

            await asyncio.sleep(2)

        raise RuntimeError("⏰ Таймаут обработки (3 минуты)")


async def show_results(job: dict, chat_id: int) -> None:
    """Отображение финальных результатов"""
    global application
    analysis = job.get("analysis", {})

    # Основные данные
    job_id = job.get("job_id", "—")
    summary = analysis.get("summary", "Резюме недоступно")
    tasks = analysis.get("tasks", [])

    # Форматируем задачи
    tasks_text = "✅ *Задачи не найдены*"
    if tasks:
        tasks_text = ""
        for i, task in enumerate(tasks, 1):
            desc = task.get("description", task.get("task", "—"))
            meta = []
            if deadline := task.get("deadline"):
                meta.append(f"📅 {deadline}")
            if assignee := task.get("assignee"):
                meta.append(f"👤 {assignee}")
            meta_str = f" ({', '.join(meta)})" if meta else ""
            tasks_text += f"{i}. {desc}{meta_str}\n"

    # Документы
    docs = []
    if doc_url := analysis.get("doc_url"):
        docs.append(f"📝 [Google Doc]({doc_url})")
    if sheet_url := analysis.get("sheet_url"):
        if sheet_url != "Нет задач для экспорта":
            docs.append(f"📊 [Google Sheet]({sheet_url})")

    docs_text = "\n".join(docs) if docs else "📄 Документы создаются автоматически"

    # Формируем сообщение
    text = (
        f"🎉 *РЕЗУЛЬТАТ ГОТОВ!*\n\n"
        f"🆔 *Job ID:* `{job_id}`\n\n"
        f"📋 *РЕЗЮМЕ:*\n{summary}\n\n"
        f"✅ *ЗАДАЧИ ({len(tasks)}):*\n{tasks_text}\n\n"
        f"🔗 *ДОКУМЕНТЫ:*\n{docs_text}"
    )

    # Клавиатура
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎙️ Новое аудио", callback_data="new_audio"),
            InlineKeyboardButton("📊 Swagger", url="https://httpbin.org/anything")
        ]
    ])
    logger.info(f"Swagger URL button: {API_BASE_URL.rstrip('/') + '/docs'}")

    await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )


async def new_audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопка "Новое аудио"""
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    await query.message.reply_text(
        "✅ *Готов к новому аудио!* 🎧\n\n"
        "Отправь голосовое или аудио файл!",
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текстовых сообщений"""
    await update.message.reply_text(
        "🎙️ *Пришли голосовое или аудио!*\n\n"
        "/start — начать\n"
        "/help — инструкция",
        parse_mode=ParseMode.MARKDOWN
    )


def cleanup_file(file_path: str) -> None:
    """Удаление временного файла"""
    try:
        if file_path and Path(file_path).exists():
            Path(file_path).unlink()
            logger.info(f"Cleaned up: {file_path}")
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")


def main() -> None:
    """Главная функция запуска"""
    global application

    print("🤖 Voice2Action Bot v2.2 (v21+)")
    print(f"📡 Backend: {API_BASE_URL}")
    print("🚀 Создание приложения...")

    # Создаём приложение v21+
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.add_handler(CallbackQueryHandler(analysis_choice, pattern="^(auto|meeting|sales|interview|lecture)$"))
    application.add_handler(CallbackQueryHandler(new_audio_handler, pattern="^new_audio$"))

    print("✅ Бот запущен! Отправь /start в Telegram")
    print("🛑 Ctrl+C для остановки")

    # Запуск polling
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
