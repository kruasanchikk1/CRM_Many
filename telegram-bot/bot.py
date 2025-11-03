import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Импорты сервисов (используем те же, что и в backend)
import sys
sys.path.append('../backend')
from services.transcription import transcribe_audio
from services.analysis import analyze_transcript
from services.excel_generator import generate_excel
from services.word_generator import generate_word
from services.jira_service import create_jira_issues
from services.gdocs_service import create_google_doc

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    welcome_text = """
👋 Добро пожаловать в Voice2Action!

Я превращаю ваши голосовые встречи в готовые документы и задачи.

🎙 **Как использовать:**
1. Отправь мне голосовое сообщение или аудио файл
2. Выбери тип анализа (встреча, продажи, интервью)
3. Выбери куда экспортировать (Excel, Word, Jira, Google Docs)
4. Получи готовые результаты!

📋 **Команды:**
/help - Помощь
/feedback - Отправить отзыв

⚡️ Давай начнём! Отправь аудио файл.
"""
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
📚 **Возможности Voice2Action:**

🎯 **Типы анализа:**
• Встреча - Summary + задачи + протокол
• Продажи - Анализ звонка + рекомендации
• Интервью - Оценка кандидата
• Кастом - Свой промпт

📤 **Экспорт:**
• Excel - Таблица с задачами
• Word - Официальный протокол
• Jira - Автоматическое создание тикетов
• Google Docs - Документ в вашем Drive

⚙️ **Поддерживаемые форматы:**
MP3, OGG, WAV, M4A (до 20 МБ, до 3 часов)

💡 **Совет:** Записывай встречи в хорошем качестве для лучшего результата!
"""
    await update.message.reply_text(help_text)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка голосового сообщения или аудио файла"""
    message = update.message
    user_id = message.from_user.id
    
    # Определяем тип аудио
    if message.voice:
        file = await message.voice.get_file()
        file_path = f'/tmp/temp_{user_id}_{file.file_id}.ogg'
    elif message.audio:
        file = await message.audio.get_file()
        file_path = f'/tmp/temp_{user_id}_{file.file_id}.mp3'
    else:
        await message.reply_text("Пожалуйста, отправь голосовое сообщение или аудио файл.")
        return
    
    # Скачиваем файл
    await file.download_to_drive(file_path)
    
    # Сохраняем путь в контексте пользователя
    context.user_data['audio_file'] = file_path
    
    await message.reply_text('🎧 Аудио получено!')
    
    # Показываем меню выбора типа анализа
    keyboard = [
        [InlineKeyboardButton("📊 Встреча", callback_data="analysis_meeting")],
        [InlineKeyboardButton("💼 Продажи", callback_data="analysis_sales")],
        [InlineKeyboardButton("👤 Интервью", callback_data="analysis_interview")],
        [InlineKeyboardButton("✏️ Кастом", callback_data="analysis_custom")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "Выбери тип анализа:",
        reply_markup=reply_markup
    )


async def button_analysis_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора типа анализа"""
    query = update.callback_query
    await query.answer()
    
    analysis_type = query.data.split("_")[1]
    context.user_data['analysis_type'] = analysis_type
    
    # Если кастом - запрашиваем промпт
    if analysis_type == "custom":
        await query.edit_message_text(
            "✏️ Отправь свой промпт для анализа\n\nИспользуй {transcript} для вставки транскрипта."
        )
        context.user_data['awaiting_custom_prompt'] = True
        return
    
    # Иначе переходим к выбору экспорта
    await show_export_menu(query, context)


async def show_export_menu(query_or_message, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню выбора экспорта"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Excel", callback_data="export_excel"),
            InlineKeyboardButton("📄 Word", callback_data="export_word")
        ],
        [
            InlineKeyboardButton("🎫 Jira", callback_data="export_jira"),
            InlineKeyboardButton("📝 Google Docs", callback_data="export_gdocs")
        ],
        [InlineKeyboardButton("✅ Готово (начать)", callback_data="export_done")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "Выбери форматы экспорта (можно несколько):\n\n"
    
    # Показываем уже выбранные
    selected = context.user_data.get('exports', [])
    if selected:
        text += "✅ Выбрано: " + ", ".join(selected) + "\n\n"
    
    text += "Нажми 'Готово' для запуска обработки."
    
    if hasattr(query_or_message, 'edit_message_text'):
        await query_or_message.edit_message_text(text, reply_markup=reply_markup)
    else:
        await query_or_message.reply_text(text, reply_markup=reply_markup)


async def button_export_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора формата экспорта"""
    query = update.callback_query
    await query.answer()
    
    export_type = query.data.split("_")[1]
    
    if export_type == "done":
        # Запускаем обработку
        await start_processing(query, context)
    else:
        # Добавляем/убираем формат из списка
        exports = context.user_data.get('exports', [])
        
        if export_type in exports:
            exports.remove(export_type)
        else:
            exports.append(export_type)
        
        context.user_data['exports'] = exports
        
        # Обновляем меню
        await show_export_menu(query, context)


async def start_processing(query, context: ContextTypes.DEFAULT_TYPE):
    """Запуск обработки аудио"""
    await query.edit_message_text("⏳ Начинаю обработку...")
    
    file_path = context.user_data.get('audio_file')
    analysis_type = context.user_data.get('analysis_type', 'meeting')
    custom_prompt = context.user_data.get('custom_prompt')
    exports = context.user_data.get('exports', [])
    
    if not file_path:
        await query.message.reply_text("Ошибка: аудио файл не найден. Отправь файл заново.")
        return
    
    if not exports:
        await query.message.reply_text("Выбери хотя бы один формат экспорта!")
        await show_export_menu(query.message, context)
        return
    
    try:
        # Шаг 1: Транскрибация
        await query.message.reply_text("🎯 Транскрибирую аудио...")
        transcript_data = await transcribe_audio(file_path)
        transcript = transcript_data["text"]
        
        # Шаг 2: Анализ
        await query.message.reply_text("🧠 Анализирую содержание...")
        analysis = await analyze_transcript(
            transcript, 
            analysis_type=analysis_type,
            custom_prompt=custom_prompt
        )
        
        # Шаг 3: Экспорт
        results = []
        
        if 'excel' in exports:
            await query.message.reply_text("📊 Создаю Excel...")
            excel_path = generate_excel(analysis, transcript)
            await query.message.reply_document(
                document=open(excel_path, 'rb'),
                filename="analysis.xlsx"
            )
            os.remove(excel_path)
            results.append("✅ Excel")
        
        if 'word' in exports:
            await query.message.reply_text("📄 Создаю Word...")
            word_path = generate_word(analysis, transcript)
            await query.message.reply_document(
                document=open(word_path, 'rb'),
                filename="protocol.docx"
            )
            os.remove(word_path)
            results.append("✅ Word")
        
        if 'jira' in exports:
            await query.message.reply_text("🎫 Создаю задачи в Jira...")
            tasks = parse_tasks(analysis)
            jira_issues = create_jira_issues(tasks)
            
            jira_text = "✅ Jira тикеты:\n"
            for issue in jira_issues:
                jira_text += f"• {issue['key']}: {issue['url']}\n"
            
            await query.message.reply_text(jira_text)
            results.append("✅ Jira")
        
        if 'gdocs' in exports:
            await query.message.reply_text("📝 Создаю Google Doc...")
            doc_url = create_google_doc(transcript, analysis)
            await query.message.reply_text(f"✅ Google Doc: {doc_url}")
            results.append("✅ Google Docs")
        
        # Финальное сообщение
        summary = extract_summary(analysis)
        
        final_message = f"""
✅ **Обработка завершена!**

📋 **Summary:**
{summary}

📤 **Экспорт:**
{chr(10).join(results)}

⏱ Время обработки: {transcript_data.get('duration', 0) / 60:.1f} мин
"""
        
        await query.message.reply_text(final_message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        await query.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    finally:
        # Очистка
        if os.path.exists(file_path):
            os.remove(file_path)
        context.user_data.clear()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений (для кастомных промптов)"""
    if context.user_data.get('awaiting_custom_prompt'):
        context.user_data['custom_prompt'] = update.message.text
        context.user_data['awaiting_custom_prompt'] = False
        
        await update.message.reply_text("✅ Промпт сохранён!")
        await show_export_menu(update.message, context)
    else:
        await update.message.reply_text(
            "Отправь голосовое сообщение или аудио файл для обработки.\n"
            "Используй /help для справки."
        )


async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /feedback"""
    if context.args:
        feedback_text = ' '.join(context.args)
        logger.info(f"Feedback from {update.message.from_user.id}: {feedback_text}")
        await update.message.reply_text("Спасибо за отзыв! Мы обязательно его учтём.")
    else:
        await update.message.reply_text(
            "Отправь отзыв командой:\n/feedback Ваш текст здесь"
        )


def parse_tasks(analysis: str) -> list:
    """Парсинг задач из анализа"""
    tasks = []
    lines = analysis.split('\n')
    
    current_task = None
    for line in lines:
        if 'Задача:' in line:
            if current_task:
                tasks.append(current_task)
            
            current_task = {
                'description': line.split('Задача:')[1].strip(),
                'deadline': 'Не указан',
                'assignee': 'Не указан',
                'priority': 'Средний'
            }
        elif current_task:
            if 'Дедлайн:' in line:
                current_task['deadline'] = line.split('Дедлайн:')[1].strip()
            elif 'Ответственный:' in line:
                current_task['assignee'] = line.split('Ответственный:')[1].strip()
            elif 'Приоритет:' in line:
                current_task['priority'] = line.split('Приоритет:')[1].strip()
    
    if current_task:
        tasks.append(current_task)
    
    return tasks


def extract_summary(analysis: str) -> str:
    """Извлечение summary"""
    lines = analysis.split('\n')
    summary_lines = []
    in_summary = False
    
    for line in lines:
        if 'Summary' in line or 'Резюме' in line:
            in_summary = True
            continue
        if in_summary:
            if line.strip().startswith('##'):
                break
            if line.strip():
                summary_lines.append(line.strip())
    
    return ' '.join(summary_lines)[:300] + "..." if summary_lines else "Резюме не найдено"


def main():
    """Запуск бота"""
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("feedback", feedback))
    
    # Аудио
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    
    # Текст (для кастомных промптов)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_analysis_type, pattern="^analysis_"))
    app.add_handler(CallbackQueryHandler(button_export_type, pattern="^export_"))
    
    logger.info("Bot started")
    app.run_polling()


if __name__ == '__main__':
    main()
