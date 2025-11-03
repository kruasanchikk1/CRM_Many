# Voice2Action - Инструкция по установке и запуску

## 📋 Требования

- Python 3.10+
- pip
- Аккаунты:
  - OpenAI API
  - Telegram Bot Token
  - Jira Cloud (опционально)
  - Google Cloud (для Docs API, опционально)

---

## 🚀 Быстрый старт (локально)

### 1. Установка зависимостей

```bash
# Клонировать репозиторий
git clone https://github.com/yourusername/voice2action.git
cd voice2action

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Скопируй `.env.example` в `.env`:

```bash
cp .env.example .env
```

Заполни переменные в `.env`:

```bash
# Обязательные
TELEGRAM_TOKEN=твой_telegram_bot_token
OPENAI_API_KEY=sk-proj-твой_ключ

# Опциональные (для полного функционала)
JIRA_URL=https://your-company.atlassian.net
JIRA_EMAIL=bot@company.com
JIRA_API_TOKEN=твой_jira_токен
JIRA_PROJECT_KEY=V2A

GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
GOOGLE_DOCS_FOLDER_ID=id_папки_в_drive
```

### 3. Получение API ключей

#### Telegram Bot Token
1. Найди @BotFather в Telegram
2. Отправь `/newbot`
3. Следуй инструкциям
4. Скопируй токен

#### OpenAI API Key
1. Зайди на https://platform.openai.com/api-keys
2. Создай новый API ключ
3. Скопируй (сохрани, он покажется только раз!)

#### Jira API Token (опционально)
1. Зайди на https://id.atlassian.com/manage-profile/security/api-tokens
2. Create API token
3. Скопируй токен

#### Google Service Account (опционально)
1. Зайди на https://console.cloud.google.com
2. Создай проект
3. Включи Google Docs API и Google Drive API
4. Создай Service Account
5. Скачай JSON ключ как `service-account.json`
6. Создай папку в Google Drive и дай доступ Service Account

### 4. Запуск Backend (FastAPI)

```bash
# В одном терминале
python -m uvicorn backend.main:app --reload --port 8000
```

Проверь: http://localhost:8000 → должно показать `{"message": "Voice2Action API v1.0"}`

### 5. Запуск Telegram Bot

```bash
# В другом терминале
python telegram-bot/bot_v2.py
```

Проверь: отправь `/start` боту в Telegram

### 6. Открой сайт

```bash
# Просто открой в браузере
open index.html  # Mac
start index.html  # Windows
xdg-open index.html  # Linux
```

Для загрузки аудио открой `app.html`

---

## 🌐 Деплой на Render.com

### 1. Подготовка

Убедись что у тебя есть:
- Аккаунт на https://render.com
- GitHub репозиторий с проектом
- Все переменные окружения готовы

### 2. Подключение репозитория

1. Зайди на https://dashboard.render.com
2. New → Blueprint
3. Выбери свой GitHub репозиторий
4. Render автоматически обнаружит `render.yaml`

### 3. Настройка переменных окружения

В дашборде Render для каждого сервиса:

**voice2action-api**:
- OPENAI_API_KEY
- JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN (если используешь)
- GOOGLE_APPLICATION_CREDENTIALS (скопируй содержимое JSON)

**voice2action-bot**:
- TELEGRAM_TOKEN
- OPENAI_API_KEY
- (остальные по необходимости)

### 4. Деплой

Render автоматически задеплоит при пуше в `main`:

```bash
git add .
git commit -m "Deploy to Render"
git push origin main
```

### 5. Проверка

- API: https://voice2action-api.onrender.com
- Бот: отправь `/start` в Telegram
- Сайт: задеплой на GitHub Pages или Netlify

---

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=backend --cov=telegram-bot

# Только unit тесты
pytest tests/unit/

# Только интеграционные
pytest tests/integration/
```

---

## 📁 Структура проекта

```
voice2action/
├── backend/
│   ├── main.py                # FastAPI приложение
│   ├── services/
│   │   ├── transcription.py   # Whisper API
│   │   ├── analysis.py        # GPT-4o-mini
│   │   ├── excel_generator.py # Excel экспорт
│   │   ├── word_generator.py  # Word экспорт
│   │   ├── jira_service.py    # Jira интеграция
│   │   └── gdocs_service.py   # Google Docs
│   └── __init__.py
│
├── telegram-bot/
│   ├── bot_v2.py              # Telegram бот
│   └── __init__.py
│
├── frontend/
│   ├── index.html             # Главная страница
│   ├── app.html               # Форма загрузки
│   ├── features.html
│   ├── pricing.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
│
├── tests/
│   ├── test_transcription.py
│   ├── test_analysis.py
│   └── test_integrations.py
│
├── requirements.txt           # Python зависимости
├── render.yaml                # Конфиг для Render.com
├── .env.example               # Пример переменных
├── .gitignore
└── README.md
```

---

## 🔧 Настройка Google Docs API

1. **Создай Service Account**:
   - https://console.cloud.google.com
   - IAM & Admin → Service Accounts → Create Service Account
   - Скачай JSON ключ

2. **Включи API**:
   - APIs & Services → Library
   - Найди "Google Docs API" → Enable
   - Найди "Google Drive API" → Enable

3. **Создай папку в Drive**:
   - Создай папку для документов
   - Share → Добавь email Service Account (из JSON) с правами Editor
   - Скопируй ID папки из URL (строка после `/folders/`)

4. **Настрой переменные**:
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
   GOOGLE_DOCS_FOLDER_ID=твой_folder_id
   ```

---

## 🎯 Использование

### Telegram Bot

1. Найди бота: @твой_бот
2. Отправь `/start`
3. Отправь голосовое сообщение или аудио файл
4. Выбери тип анализа (встреча/продажи/интервью)
5. Выбери форматы экспорта (Excel/Word/Jira/Docs)
6. Нажми "Готово"
7. Получи результаты!

### Веб-приложение

1. Открой https://твой-сайт.com/app.html
2. Перетащи аудио файл или выбери через кнопку
3. Выбери настройки
4. Нажми "Начать обработку"
5. Скачай результаты

### API (для разработчиков)

```python
import requests

# Загрузка аудио
files = {'audio': open('meeting.mp3', 'rb')}
response = requests.post('http://localhost:8000/api/process-audio', files=files)
job_id = response.json()['job_id']

# Проверка статуса
status = requests.get(f'http://localhost:8000/api/status/{job_id}').json()
print(status['progress'], status['status'])

# Экспорт
exports = {'job_id': job_id, 'exports': ['excel', 'word']}
result = requests.post('http://localhost:8000/api/export', json=exports).json()
print(result)
```

---

## 🐛 Troubleshooting

### Бот не отвечает
- Проверь `TELEGRAM_TOKEN` в `.env`
- Убедись что бот запущен: `python telegram-bot/bot_v2.py`
- Проверь логи

### Ошибка транскрибации
- Проверь `OPENAI_API_KEY`
- Убедись что формат аудио поддерживается (MP3, OGG, WAV)
- Проверь размер файла (<20 МБ)

### Jira не создаёт тикеты
- Проверь `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- Убедись что проект `JIRA_PROJECT_KEY` существует
- Проверь права доступа

### Google Docs ошибка
- Проверь `service-account.json`
- Убедись что API включены
- Проверь права на папку

---

## 📚 Дополнительно

- [Документация API](docs/API.md)
- [Примеры промптов](docs/PROMPTS.md)
- [FAQ](docs/FAQ.md)
- [Contributing](CONTRIBUTING.md)

---

## 💬 Поддержка

- Telegram: @твой_канал
- Email: support@voice2action.ai
- Issues: https://github.com/yourusername/voice2action/issues

---

**Voice2Action** © 2025 | Made with ❤️ and AI
