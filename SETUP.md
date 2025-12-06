```markdown
# Voice2Action - Инструкция по установке и запуску 
## 📋 Требования

- **Python 3.13** (актуально для Render)
- pip
- Аккаунты:
  - **Yandex SpeechKit** (заменил OpenAI)
  - **Telegram Bot Token**
  - **Google Cloud** (Docs/Sheets API)
  - **YandexGPT API**

---

## 🚀 Быстрый старт (локально)

### 1. Установка зависимостей

```
# Клонировать репозиторий
git clone https://github.com/kruasanchikk1/CRM_Many/tree/master
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

```
cp .env.example .env
```

Заполни переменные в `.env`:

```
# Обязательные
TELEGRAM_TOKEN=твой_telegram_bot_token
YANDEX_SPEECHKIT_API_KEY=твой_speechkit_ключ
YANDEXGPT_API_KEY=твой_yandexgpt_ключ

# Google Docs
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
GOOGLE_DOCS_FOLDER_ID=id_папки_в_drive
```

### 3. Получение API ключей

#### Telegram Bot Token
1. Найди @BotFather в Telegram
2. Отправь `/newbot`
3. Следуй инструкциям
4. Скопируй токен → @voice2action_bot

#### Yandex SpeechKit
1. https://cloud.yandex.ru/services/speechkit
2. Создай API ключ
3. Выбери ru-RU модель

#### YandexGPT
1. https://cloud.yandex.ru/services/yandexgpt
2. Создай API ключ

#### Google Service Account
1. https://console.cloud.google.com
2. Создай проект → включи Docs/Drive API
3. Service Account → скачай `service-account.json`
4. Создай папку в Drive → дай доступ Service Account [file:2]

### 4. Запуск Backend (FastAPI)

```
# В одном терминале
python -m uvicorn backend.main:app --reload --port 8000
```

✅ Проверь: https://voice2action-backend.onrender.com/docs [file:2]

### 5. Запуск Telegram Bot

```
# В другом терминале
python telegram-bot/bot.py
```

🔄 **Последний шаг**: requirements.txt фикс → git push [file:2]

### 6. Открой сайт

```
# Просто открой в браузере
open index.html  # Mac
start index.html  # Windows
xdg-open index.html  # Linux
```

🌐 **Живой**: https://voice2action.netlify.app [file:2]

---

## 🌐 Деплой на Render.com (АКТУАЛЬНО)

### 1. Подготовка
- Аккаунт: https://render.com
- GitHub репозиторий
- Free tier ($0/мес)

### 2. Backend (уже живой)
✅ **https://voice2action-api-vq9x.onrender.com**
- FastAPI + Python 3.13
- Yandex SpeechKit + YandexGPT
- Google Docs API

### 3. Telegram Bot (последний шаг)
```
🔄 voice2action-bot.onrender.com
1. requirements.txt → pip install python-telegram-bot==21.7
2. git add . && git commit -m "Fix bot deps"
3. git push origin main
4. Render auto-deploy!
```

### 4. Проверка
- ✅ API: https://voice2action-api-vq9x.onrender.com/docs
- 🔄 Bot: @voice2action_bot → `/start`
- ✅ Сайт: voice2action.netlify.app [file:2]

---

## 🎯 ИТОГ ДЕПЛОЯ (06.12.2025)

| Сервис | Статус | URL |
|--------|--------|-----|
| 🌐 **Сайт** | ✅ Живой | voice2action.netlify.app |
| 🔌 **Backend** | ✅ Живой 24/7 | voice2action-backend.onrender.com |
| 🤖 **Telegram Bot** | 🔄 Последний шаг | @voice2action_bot |
| 🧠 **Yandex SpeechKit** | ✅ ru-RU | Работает |
| 🧠 **YandexGPT** | ✅ 5 сценариев | Авто/Встреча/Продажи/Интервью/Лекция |
| 📝 **Google Docs** | ✅ Экспорт | Создаёт документы | [file:2]

---

## 📊 Технический стек (обновлено)

```
Frontend: HTML/CSS/JS → Netlify
Backend: FastAPI → Render (Python 3.13)
Bot: python-telegram-bot v21.7 → Render
AI: Yandex SpeechKit + YandexGPT
Docs: Google Docs/Sheets API
Бюджет: $0/мес (все Free tier)
```

---

## 🧪 Тестирование

```
# Все тесты
pytest

# Backend API
curl -X POST "http://localhost:8000/api/process-audio" -F "audio=@test.mp3"

# Telegram bot
python telegram-bot/bot.py
```

---

## 📁 Структура проекта (актуальная)

```
voice2action/
├── backend/                 # FastAPI ✅
│   ├── main.py
│   └── services/
│       ├── speechkit.py     # Yandex SpeechKit
│       ├── yandexgpt.py     # 5 сценариев
│       └── gdocs_service.py # Google Docs
├── telegram-bot/
│   └── bot.py              # v21.7 🔄
├── frontend/               # Netlify ✅
│   ├── index.html
│   └── app.html (drag&drop)
├── requirements.txt
├── render.yaml
└── .env.example
```

---

## 🎉 ГОТОВЫЙ ПРОДУКТ

**3 канала**:
1. 🌐 **Сайт**: voice2action.netlify.app (drag&drop)
2. 🤖 **Telegram**: @voice2action_bot (голосовые)
3. 🔌 **API**: voice2action-backend.onrender.com/docs

**Рабочий процесс**:
```
📱 Голосовое → 🎧 SpeechKit → 📝 Текст → 🧠 YandexGPT → ✅ Google Docs (30-90 сек)
```

**Осталось**: `git push` → бот онлайн навсегда! 🚀 
```