
# Voice2Action - Technical Specification v2.0

## 1. System Overview

### 1.1 Purpose
Voice2Action преобразует аудиозаписи встреч в структурированные документы:
```
Аудио (.ogg/.mp3) → Yandex SpeechKit → YandexGPT → Google Docs + Sheets
```

### 1.2 Key Components
```
Frontend: Swagger UI (http://localhost:8000/docs)
Backend: FastAPI + SQLite (voice2action.db)
AI: Yandex SpeechKit + YandexGPT (yandexgpt-lite)
Export: Google Docs API + Google Sheets API
- Telegram Bot:
  - Python, python-telegram-bot v20.7
  - Обработка голосовых сообщений и аудио файлов
  - Inline keyboard для выбора задач и сервисов
- Web Application:
  - HTML/CSS/JavaScript, адаптивность под мобильные устройства и ПК
  - Загрузка аудио, просмотр статусов, результаты
- Integration Layer:
  - Plugin-based архитектура для Jira, Confluence, Notion, Google Workspace
```

## 2. Architecture Diagram

```
graph TD
    A[Клиент: POST /api/process-audio] --> B[FastAPI: job_id]
    B --> C[SQLite: jobs таблица]
    B --> D[Temp: иван.ogg]
    D --> E[Yandex SpeechKit: транскрипция]
    E --> F[YandexGPT: анализ JSON]
    F --> G[SQLite: сохранить анализ]
    F --> H[GoogleDocsService]
    H --> I[Google Docs: резюме]
    H --> J[Google Sheets: задачи]
    K[GET /api/jobs/{id}] --> G

Telegram Bot User Flow:
1. Пользователь отправляет голосовое сообщение.
2. Бот скачивает аудио, вызывает `/api/process-audio`.
3. Сообщает о ходе обработки и выдаёт ссылки на результаты.

Web User Flow:
1. Пользователь заходит на сайт.
2. Загружает аудио, выбирает задачи/сервисы.
3. Получает отчёты, экспорт в предпочтительные сервисы.
```

## 3. API Specification

### 3.1 Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `POST` | `/api/process-audio` | Загрузить аудио | `{"job_id": "...", "status_url": "..."}` |
| `GET` | `/api/jobs/{job_id}` | Полная информация | `{"transcript": "...", "analysis": {...}}` |
| `GET` | `/api/health` | Статус сервисов | `{"status": "healthy", "services": {...}}` |

### 3.2 Request/Response Examples

**Загрузка аудио:**
```
curl -X POST "http://localhost:8000/api/process-audio" \
  -F "audio=@ivan.ogg"
```
**Ответ:**
```
{
  "job_id": "94822815-6d62-42d6-bd72-8907612dbefd",
  "status_url": "/api/jobs/94822815-6d62-42d6-bd72-8907612dbefd"
}
```

**Результат анализа:**
```
{
  "job_id": "94822815-...",
  "status": "completed",
  "analysis": {
    "summary": "Игорь обсуждает бильярд на завтра",
    "tasks": [
      {
        "description": "Сходить на бильярд",
        "deadline": "завтра",
        "assignee": "Игорь",
        "priority": "Medium"
      }
    ]
  }
}
```

## 4. Data Models

### 4.1 SQLite Schema (voice2action.db)
```
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  status TEXT DEFAULT 'processing',
  created_at TEXT NOT NULL,
  completed_at TEXT,
  transcript_text TEXT,
  transcript_chars INTEGER,
  analysis TEXT,        -- JSON
  extracted_tasks TEXT  -- JSON
);
```

### 4.2 Analysis JSON Format
```
{
  "summary": "Краткое резюме (2-3 предложения)",
  "tasks": [
    {
      "description": "Текст задачи",
      "deadline": "YYYY-MM-DD или 'Не указан'",
      "assignee": "Имя или 'Не указан'",
      "priority": "High/Medium/Low"
    }
  ],
  "key_points": ["Пункт 1", "Пункт 2"],
  "decisions": ["Решение 1", "Решение 2"]
}
```

## 5. Services Implementation

### 5.1 Yandex SpeechKit (services/yandex_stt.py)
```
POST https://stt.api.cloud.yandex.net/speech/v1/stt:recognize
?folderId=b1g82ese7knalo94r5id&lang=ru-RU
```
**Параметры:** аудио bytes, lang=ru-RU  
**Ответ:** `{"result": "Игорек бильярд завтра будет"}`

### 5.2 YandexGPT (services/yandex_gpt.py)
```
POST https://llm.api.cloud.yandex.net/foundationModels/v1/completion
modelUri: gpt://b1g82ese7knalo94r5id/yandexgpt-lite
```
**Промпт:** JSON-структурированный анализ транскрипта  
**Парсинг:** Удаление ```

### 5.3 Google Docs/Sheets (services/gdocs_service.py)
- **Docs:** Создание документа + вставка Markdown
- **Sheets:** Таблица "Задачи" (4 колонки)
- **Права:** `anyone` с ролью `reader`

## 6. Environment Variables (.env)

```env
YANDEX_API_KEY=ajeimo8ioqeptc3tklp3
YANDEX_FOLDER_ID=b1g82ese7knalo94r5id
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
```

## 7. Deployment & Local Setup

### 7.1 Local Development
```bash
# Установка
pip install -r requirements.txt

# Запуск
python main.py
# API: http://localhost:8000/docs
# Health: http://localhost:8000/health
- Telegram Bot:
  - Развёрнут как worker на Render.com, поднимается автоматически.
  - Минорное логирование и мониторинг.
- Веб-сайт:
  - Статичный хостинг на GitHub Pages.
  - Бэкенд – API FastAPI + Yandex Cloud.

```

### 7.2 Production (Render/Yandex Cloud)
```
env:
  YANDEX_API_KEY: ${{YANDEX_API_KEY}}
  GOOGLE_SERVICE_ACCOUNT_JSON: ${{GOOGLE_SERVICE_ACCOUNT_JSON}}
command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

## 8. Error Handling

| Ошибка | Действие | Лог | Клиенту |
|--------|----------|-----|---------|
| Yandex 401 | Retry 3x | `ERROR: Yandex UNAUTHORIZED` | `503 Service Unavailable` |
| Google 403 | Skip Docs | `WARNING: Google Docs failed` | `200` с анализом |
| Пустой транскрипт | Fallback | `WARNING: Empty transcript` | `400 Bad Request` |

## 9. Performance Metrics

| Метрика | Текущее | Цель |
|---------|---------|------|
| Время транскрипции | 2-10s | <5s |
| Время анализа | 3-15s | <10s |
| Создание Docs | 5-20s | <10s |
| Полный пайплайн | 15-45s | <30s |

## 10. Testing Checklist

```bash
# ✅ Core functionality
python main.py                    # Сервер стартует
curl /health                      # Все сервисы healthy
curl /api/process-audio -F audio  # Job создаётся

# ✅ End-to-End
curl /api/jobs/{JOB_ID}           # Анализ + транскрипт
Google Docs ссылка работает       # Документ доступен
Google Sheets создана             # Таблица задач
```

***

**Version:** 2.0.0  
**Date:** 2025-12-03  
**Status:** Matches current implementation  
**Next:** Telegram Bot + Frontend
```
