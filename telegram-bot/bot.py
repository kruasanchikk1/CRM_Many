import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from atlassian import Jira

# Загрузка .env
load_dotenv()

# Ключи
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
JIRA_URL = os.getenv('JIRA_URL')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY')

# OpenAI клиент
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Jira клиент
jira = Jira(url=JIRA_URL, username=JIRA_EMAIL, password=JIRA_API_TOKEN, cloud=True)

# Логи
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Привет! Отправь голосовое или аудио-файл — я транскрибирую, сделаю summary и создам задачу в Jira.')


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message.voice or message.audio:
        file = await (message.voice or message.audio).get_file()
        file_path = f'temp_{file.file_id}.ogg' if message.voice else f'temp_{file.file_id}.mp3'

        # Скачиваем файл
        await file.download_to_drive(file_path)
        await message.reply_text('Аудио получено! Обрабатываю...')

        try:
            # Транскрибация (Whisper API)
            with open(file_path, 'rb') as audio_file:
                transcript = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                ).text

            # Анализ и summary (GPT)
            prompt = f"""
            Проанализируй текст: "{transcript}"
            1. Создай краткий summary.
            2. Выдели задачи (формат: - Задача: Описание [Дедлайн: дата] [Ответственный: имя]).
            3. Для продаж: Анализ стиля (слова-паразиты, паузы, уверенность).
            """
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            ).choices[0].message.content

            # Создание тикета в Jira (пример: одна задача)
            tasks = [line for line in response.split('\n') if line.startswith('- Задача:')]
            if tasks:
                issue = jira.issue_create(
                    fields={
                        'project': {'key': JIRA_PROJECT_KEY},
                        'summary': tasks[0].replace('- Задача: ', ''),
                        'description': transcript,
                        'issuetype': {'name': 'Task'}
                    }
                )
                jira_link = f"{JIRA_URL}/browse/{issue['key']}"
                response += f"\n\nСоздан тикет: {jira_link}"

            await message.reply_text(response)

        except Exception as e:
            logger.error(e)
            await message.reply_text(f'Ошибка: {str(e)}')

        # Удаляем temp файл
        os.remove(file_path)

    else:
        await message.reply_text('Отправь голосовое или аудио!')


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.run_polling()


if __name__ == '__main__':
    main()