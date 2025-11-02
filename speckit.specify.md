# Voice2Action - Technical Specification

## 1. System Overview

### 1.1 Purpose
Voice2Action is an AI-powered system that transforms voice recordings from meetings and calls into actionable documentation, tasks, and analytics. The system processes audio through speech recognition, natural language analysis, and automated task management.

### 1.2 Key Components
- **Telegram Bot**: Primary user interface for mobile users
- **Web Application**: Browser-based interface for desktop users
- **AI Processing Pipeline**: Whisper (transcription) + GPT-4o-mini (analysis)
- **Integration Layer**: Jira, Google Docs, Confluence connectors
- **Backend API**: Python FastAPI service

### 1.3 User Flow Summary
```
Audio Input → Transcription → AI Analysis → Task Creation → Delivery
(User)        (Whisper)      (GPT-4o)      (Jira API)     (Response)
```

---

## 2. Telegram Bot Workflow

### 2.1 User Interaction
**Trigger**: User sends voice message or audio file to `@voice2action_bot`

**Supported formats**:
- Voice messages (OGG/OPUS)
- Audio files (MP3, M4A, WAV, OGG)
- Maximum duration: 180 minutes
- Maximum file size: 100 MB

### 2.2 Processing Pipeline

#### Step 1: Audio Reception
```python
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    
    # Identify audio type
    if message.voice:
        file = await message.voice.get_file()
        file_path = f'temp_{file.file_id}.ogg'
    elif message.audio:
        file = await message.audio.get_file()
        file_path = f'temp_{file.file_id}.mp3'
    
    # Download file
    await file.download_to_drive(file_path)
    await message.reply_text('🎧 Аудио получено! Начинаю обработку...')
```

**Actions**:
1. Validate file format and size
2. Download to temporary storage (`/tmp/` directory)
3. Generate unique file ID for tracking
4. Send confirmation message to user

#### Step 1.5: Audio Chunking (for files >30 min)
```python
# services/audio_utils.py
from pydub import AudioSegment
import os

def get_duration(file_path):
    audio = AudioSegment.from_file(file_path)
    return len(audio) / 1000.0

def split_audio(file_path, chunk_sec=1800):  # 30 мин
    audio = AudioSegment.from_file(file_path)
    duration_ms = len(audio)
    chunks = []
    for i in range(0, duration_ms, chunk_sec * 1000):
        chunk = audio[i:i + chunk_sec * 1000]
        path = f"/tmp/chunk_{os.getpid()}_{i}.mp3"
        chunk.export(path, format="mp3")
        chunks.append(path)
    return chunks
```

#### Step 2: Audio Conversion (if needed)
```python
# Convert OGG/OPUS to MP3 for better compatibility
if file_path.endswith('.ogg'):
    mp3_path = file_path.replace('.ogg', '.mp3')
    # Use pydub or ffmpeg
    AudioSegment.from_ogg(file_path).export(mp3_path, format='mp3')
    file_path = mp3_path
```

**Requirements**:
- Ensure consistent audio format for Whisper
- Preserve audio quality (minimum 16kHz sampling rate)
- Handle corrupted files gracefully

#### Step 3: Transcription (OpenAI Whisper)
```python
from services.audio_utils import get_duration, split_audio
import asyncio
import os

async def transcribe_audio(file_path: str) -> dict:
    duration = get_duration(file_path)
    
    # Если >30 мин — разбиваем
    if duration > 1800:
        print(f"[INFO] Аудио >30 мин ({duration:.1f}с). Разбиваем...")
        chunks = split_audio(file_path)
        full_text = ""
        segments = []
        offset = 0
        
        for idx, chunk in enumerate(chunks):
            print(f"[INFO] Транскрибация части {idx+1}/{len(chunks)}")
            try:
                with open(chunk, "rb") as f:
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
                offset += get_duration(chunk)
            finally:
                if os.path.exists(chunk):
                    os.remove(chunk)
        
        return {"text": full_text.strip(), "segments": segments, "duration": duration}
    
    # Обычная транскрибация
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
            "segments": result.segments,
            "duration": duration
        }
```

**API Parameters**:
- `model`: `whisper-1` (most accurate)
- `language`: `ru` (Russian, auto-detect if needed)
- `response_format`: `verbose_json` (includes timestamps)
- `temperature`: `0.0-0.2` (lower = more accurate)

**Error Handling**:
- Timeout: Retry up to 3 times with exponential backoff
- Invalid audio: Notify user "Не удалось распознать аудио"
- API quota exceeded: Queue request for later processing

**Expected Output**:
```json
{
  "text": "Добрый день коллеги. Обсудим задачи на спринт...",
  "segments": [
    {"start": 0.0, "end": 3.5, "text": "Добрый день коллеги."},
    {"start": 3.5, "end": 7.2, "text": "Обсудим задачи на спринт..."}
  ],
  "language": "ru"
}
```

#### Step 4: AI Analysis (GPT-4o-mini)

#### Step 4.1: Select Analysis Type
```python
## После получения аудио
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

await message.reply_text(
    "Выберите тип анализа:",
    reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Встреча", callback_data="analysis_meeting")],
        [InlineKeyboardButton("Продажи", callback_data="analysis_sales")],
        [InlineKeyboardButton("Интервью", callback_data="analysis_interview")],
        [InlineKeyboardButton("Кастом", callback_data="analysis_custom")],
    ])
)
# Сохрани выбор
context.user_data['analysis_type'] = query.data.split("_")[1]
```
```python
prompt = f"""
Проанализируй транскрипт встречи и выполни следующее:

**Транскрипт:**
{transcript.text}

**Задачи:**
1. Создай краткое резюме (summary) встречи (3-5 предложений).
2. Извлеки все задачи в формате:
   - Задача: [Краткое описание]
   - Дедлайн: [Дата или "Не указан"]
   - Ответственный: [Имя или "Не указан"]
   
3. Если это звонок продаж, добавь анализ стиля:
   - Слова-паразиты (эээ, ммм, типа)
   - Длительные паузы (>3 секунд)
   - Уверенность речи (Высокая/Средняя/Низкая)
   - Рекомендации для улучшения

**Формат ответа:**
## Summary
[Резюме встречи]

## Задачи
1. Задача: [Описание]
   Дедлайн: [Дата]
   Ответственный: [Имя]

## Анализ (если применимо)
[Анализ стиля коммуникации]
"""

response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Ты ассистент для анализа деловых встреч и звонков."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.3,
    max_tokens=1500
)

analysis = response.choices[0].message.content
```

**Prompt Engineering Best Practices**:
- Clear structure with numbered instructions
- Explicit output format (markdown sections)
- Contextual awareness (sales call vs meeting)
- Fallback for missing information ("Не указан")

**Expected Output**:
```markdown
## Summary
Обсуждение спринта 45. Команда согласовала 5 задач на неделю. Основной фокус - рефакторинг модуля авторизации и новый API endpoint.

## Задачи
1. Задача: Рефакторинг модуля авторизации
   Дедлайн: 2025-11-08
   Ответственный: Алексей

2. Задача: Создать API для экспорта отчетов
   Дедлайн: 2025-11-10
   Ответственный: Мария

## Анализ
Уверенность речи: Высокая
Слова-паразиты: 3 случая ("эээ")
Рекомендации: Отличная коммуникация, четкие формулировки
```

#### Step 5: Jira Integration
```python
# Parse tasks from GPT response
tasks = parse_tasks_from_analysis(analysis)

created_issues = []
for task in tasks:
    issue = jira.issue_create(
        fields={
            'project': {'key': JIRA_PROJECT_KEY},  # e.g., "V2A"
            'summary': task['description'],
            'description': f"""
Источник: Voice2Action Bot
Создано: {datetime.now().isoformat()}
Дедлайн: {task['deadline']}
Ответственный: {task['assignee']}

Полный транскрипт:
{transcript.text[:500]}...
            """,
            'issuetype': {'name': 'Task'},
            'priority': {'name': 'Medium'},
            'duedate': task['deadline'] if task['deadline'] != 'Не указан' else None
        }
    )
    
    created_issues.append({
        'key': issue['key'],
        'url': f"{JIRA_URL}/browse/{issue['key']}"
    })
```

**Jira API Requirements**:
- Authentication: Basic Auth (email + API token) or OAuth 2.0
- Endpoint: `POST /rest/api/3/issue`
- Fields: `project`, `summary`, `description`, `issuetype`, `duedate`
- Error handling: Handle duplicate issues, invalid project keys

**Rate Limiting**:
- Jira Cloud: 100 requests/minute
- Implement exponential backoff on 429 errors

#### Step 6: Google Docs Export (Optional)
```python
# Create document via Google Docs API
from googleapiclient.discovery import build

service = build('docs', 'v1', credentials=creds)

document = service.documents().create(
    body={
        'title': f'Voice2Action Protocol - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
    }
).execute()

doc_id = document['documentId']

# Insert content
requests = [
    {
        'insertText': {
            'location': {'index': 1},
            'text': f"{analysis}\n\n--- Транскрипт ---\n{transcript.text}"
        }
    }
]

service.documents().batchUpdate(
    documentId=doc_id,
    body={'requests': requests}
).execute()

doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
```

**Google API Setup**:
- Enable Google Docs API in Cloud Console
- OAuth 2.0 credentials with `docs` scope
- Service account for server-to-server auth
- Share document publicly or with specific users

**Fallback Strategy** (if API unavailable):
- Generate markdown file
- Upload to file hosting (Dropbox, OneDrive)
- Send direct link to user

#### Step 7: Response to User

###  **Step 7.1: Export Options**

```markdown
#### Step 7.1: Export Options
```python
await message.reply_text(
    "Куда экспортировать?",
    reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Excel", callback_data="export_excel")],
        [InlineKeyboardButton("Word", callback_data="export_word")],
        [InlineKeyboardButton("Jira", callback_data="export_jira")],
        [InlineKeyboardButton("Google Docs", callback_data="export_gdocs")],
    ])
)
```
## Excel Export (services/excel_generator.py)
```python
from openpyxl import Workbook

from openpyxl.styles import Font, PatternFill

def generate_excel(analysis, transcript=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws['A1'] = "Анализ встречи"
    ws['A1'].font = Font(size=16, bold=True)
    # ... (весь код из v2.0)
    path = f"/tmp/analysis_{job_id}.xlsx"
    wb.save(path)
    return path
```

Word Export (services/word_generator.py)
```python
from docx import Document

def generate_word(analysis, transcript=None):
    doc = Document()
    doc.add_heading('ПРОТОКОЛ ВСТРЕЧИ', 0)
    # ... (весь код из v2.0)
    path = f"/tmp/protocol_{job_id}.docx"
    doc.save(path)
    return path
```

```python
response_message = f"""
✅ **Обработка завершена!**

📝 **Summary:**
{extract_summary(analysis)}

📋 **Задачи:**
{format_tasks_for_telegram(tasks)}

🔗 **Ссылки:**
{format_jira_links(created_issues)}
{f"📄 [Google Doc]({doc_url})" if doc_url else ""}

⏱ Время обработки: {processing_time:.1f} сек
"""

await message.reply_text(
    response_message,
    parse_mode='Markdown',
    disable_web_page_preview=True
)

# Cleanup temp files
os.remove(file_path)
```

**Message Formatting**:
- Use Telegram markdown (bold, links, lists)
- Include emojis for visual clarity
- Limit message length (4096 chars max)
- Split long messages if needed

---

## 3. Web Application Workflow

### 3.1 User Interface
**URL**: `https://voice2action.ai/app`

**Features**:
- Drag-and-drop audio upload
- File selection dialog (button)
- Progress indicator during processing
- Real-time status updates via WebSocket

### 3.2 Frontend Implementation

#### HTML Structure
```html
<!-- app.html -->
<div class="upload-section">
  <div class="drop-zone" id="dropZone">
    <p>Перетащите аудиофайл сюда или</p>
    <button class="btn primary-btn" onclick="document.getElementById('fileInput').click()">
      Выберите файл
    </button>
    <input type="file" id="fileInput" accept="audio/*" hidden>
  </div>
  
  <div class="progress-container" id="progressContainer" hidden>
    <div class="progress-bar">
      <div class="progress-fill" id="progressFill"></div>
    </div>
    <p class="progress-text" id="progressText">Загрузка...</p>
  </div>
  
  <div class="results-container" id="resultsContainer" hidden>
    <!-- Results will be injected here -->
  </div>
</div>
```

#### JavaScript Upload Handler
```javascript
// app.js
const fileInput = document.getElementById('fileInput');
const dropZone = document.getElementById('dropZone');
const progressContainer = document.getElementById('progressContainer');
const resultsContainer = document.getElementById('resultsContainer');

fileInput.addEventListener('change', handleFileUpload);
dropZone.addEventListener('drop', handleDrop);
dropZone.addEventListener('dragover', (e) => e.preventDefault());

async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  // Validate file
  const validTypes = ['audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/mp4'];
  if (!validTypes.includes(file.type)) {
    alert('Неподдерживаемый формат. Используйте MP3, OGG, WAV или M4A.');
    return;
  }
  
  if (file.size > 20 * 1024 * 1024) { // 20 MB
    alert('Файл слишком большой. Максимум 20 МБ.');
    return;
  }
  
  // Show progress
  dropZone.hidden = true;
  progressContainer.hidden = false;
  updateProgress(0, 'Загрузка файла...');
  
  // Upload to backend
  const formData = new FormData();
  formData.append('audio', file);
  
  try {
    const response = await fetch('/api/process-audio', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) throw new Error('Upload failed');
    
    // Poll for results
    const jobId = (await response.json()).job_id;
    pollProcessingStatus(jobId);
    
  } catch (error) {
    showError('Ошибка загрузки: ' + error.message);
  }
}

async function pollProcessingStatus(jobId) {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/status/${jobId}`);
    const data = await response.json();
    
    updateProgress(data.progress, data.status);
    
    if (data.complete) {
      clearInterval(interval);
      displayResults(data.results);
    }
    
    if (data.error) {
      clearInterval(interval);
      showError(data.error);
    }
  }, 2000); // Poll every 2 seconds
}

function displayResults(results) {
  progressContainer.hidden = true;
  resultsContainer.hidden = false;
  
  resultsContainer.innerHTML = `
    <h2>✅ Обработка завершена</h2>
    
    <section class="summary-section">
      <h3>📝 Summary</h3>
      <p>${results.summary}</p>
    </section>
    
    <section class="tasks-section">
      <h3>📋 Задачи</h3>
      <ul>
        ${results.tasks.map(task => `
          <li>
            <strong>${task.description}</strong><br>
            Дедлайн: ${task.deadline} | Ответственный: ${task.assignee}
          </li>
        `).join('')}
      </ul>
    </section>
    
    <section class="links-section">
      <h3>🔗 Ссылки</h3>
      ${results.jira_issues.map(issue => `
        <a href="${issue.url}" target="_blank">${issue.key}</a>
      `).join(' | ')}
      ${results.doc_url ? `<br><a href="${results.doc_url}" target="_blank">📄 Google Doc</a>` : ''}
    </section>
    
    <button class="btn secondary" onclick="resetForm()">
      Обработать ещё один файл
    </button>
  `;
}
```

### 3.3 Backend API

#### FastAPI Endpoints
```python
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
import uuid

app = FastAPI()

# In-memory job storage (use Redis in production)
jobs = {}

@app.post("/api/export")
async def export_results(request: ExportRequest, background: BackgroundTasks):
    job = await get_job(request.job_id)
    if not job.complete:
        raise HTTPException(400, "Job not completed")
    
    results = []
    if "excel" in request.exports:
        path = generate_excel(job.results)
        background.add_task(os.remove, path)  # cleanup
        results.append({"type": "excel", "url": f"/download/excel/{job.id}"})
    
    return {"exports": results}

@app.post("/api/process-audio")
async def process_audio(audio: UploadFile, background_tasks: BackgroundTasks):
    """
    Endpoint to upload audio file and start processing
    """
    # Validate file
    if audio.content_type not in ['audio/mpeg', 'audio/ogg', 'audio/wav']:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid file type"}
        )
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Save file temporarily
    file_path = f"/tmp/{job_id}_{audio.filename}"
    with open(file_path, "wb") as f:
        f.write(await audio.read())
    
    # Initialize job status
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "complete": False,
        "error": None,
        "results": None
    }
    
    # Start background processing
    background_tasks.add_task(process_audio_pipeline, job_id, file_path)
    
    return {"job_id": job_id}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """
    Poll endpoint for job status
    """
    if job_id not in jobs:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    
    return jobs[job_id]

async def process_audio_pipeline(job_id: str, file_path: str):
    """
    Background task for audio processing
    """
    try:
        # Step 1: Transcription
        jobs[job_id].update({"status": "Транскрибация...", "progress": 20})
        transcript = await transcribe_audio(file_path)
        
        # Step 2: AI Analysis
        jobs[job_id].update({"status": "Анализ текста...", "progress": 50})
        analysis = await analyze_transcript(transcript)
        
        # Step 3: Jira Integration
        jobs[job_id].update({"status": "Создание задач...", "progress": 75})
        jira_issues = await create_jira_issues(analysis['tasks'])
        
        # Step 4: Google Docs (optional)
        jobs[job_id].update({"status": "Создание документа...", "progress": 90})
        doc_url = await create_google_doc(transcript, analysis)
        
        # Complete
        jobs[job_id].update({
            "status": "Готово",
            "progress": 100,
            "complete": True,
            "results": {
                "summary": analysis['summary'],
                "tasks": analysis['tasks'],
                "jira_issues": jira_issues,
                "doc_url": doc_url
            }
        })
        
    except Exception as e:
        jobs[job_id].update({
            "status": "Ошибка",
            "error": str(e),
            "complete": True
        })
    
    finally:
        # Cleanup
        os.remove(file_path)
```

---

## 4. Data Flow Architecture

```
┌─────────────────┐
│   User Input    │
│  (Audio File)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  File Storage   │◄──── Validation (format, size)
│   (Temp /tmp)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ OpenAI Whisper  │◄──── API Call (30-120s)
│  Transcription  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GPT-4o-mini    │◄──── Prompt Engineering
│    Analysis     │      (Summary + Tasks + Style)
└────────┬────────┘
         │
         ├─────────────────────┐
         │                     │
         ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│   Jira REST     │   │  Google Docs    │
│      API        │   │      API        │
│ (Create Issues) │   │ (Create Doc)    │
└────────┬────────┘   └────────┬────────┘
         │                     │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────┐
         │   Response to   │
         │      User       │
         │ (Telegram/Web)  │
         └─────────────────┘
```

---

## 5. Error Handling & Edge Cases

### 5.1 Audio Processing Errors

| Error | Cause | Handling |
|-------|-------|----------|
| `Invalid format` | Unsupported file type | Notify user, suggest MP3/OGG |
| `File too large` | >20 MB | Notify user, request shorter audio |
| `Corrupted audio` | Damaged file | Notify user to re-record |
| `Empty audio` | Silent recording | Notify user "Аудио не содержит речи" |

### 5.2 API Errors

| Error | Cause | Handling |
|-------|-------|----------|
| `Whisper timeout` | Large file, slow API | Retry 3x with backoff, then notify |
| `GPT rate limit` | Too many requests | Queue job, process when quota available |
| `Jira auth failed` | Invalid credentials | Log error, skip Jira, continue with summary |
| `Google Docs quota` | Daily limit exceeded | Skip Doc creation, use markdown export |

### 5.3 Network Issues
- **Telegram bot disconnect**: Automatic reconnection via `python-telegram-bot`
- **API downtime**: Fallback to cached responses or queue for later
- **Database unavailable**: Use in-memory storage temporarily

---

## 6. Performance Requirements

### 6.1 Response Times
- **Telegram bot response**: <2 seconds for acknowledgment
- **Transcription (Whisper)**: 30-120 seconds (depends on audio length)
- **AI analysis (GPT-4o-mini)**: 5-15 seconds
- **Jira ticket creation**: 2-5 seconds per task
- **Total pipeline**: <3 minutes for 10-minute audio

### 6.2 Scalability
- **Concurrent users**: Support 100+ simultaneous requests
- **Daily processing**: 1,000+ audio files per day
- **Storage**: Auto-delete temp files after 24 hours
- **Rate limiting**: 10 requests/minute per user

### 6.3 Uptime
- **Telegram bot**: 99.5% uptime (monitored via UptimeRobot)
- **Web app**: 99.9% uptime (hosted on Render.com)
- **Database**: PostgreSQL with automatic backups

---

## 7. Security & Privacy

### 7.1 Data Protection
- **Encryption in transit**: HTTPS/TLS for all API calls
- **Encryption at rest**: AES-256 for stored audio (if needed)
- **Data retention**: Audio deleted after processing (max 24h)
- **GDPR compliance**: User consent for data processing

### 7.2 Authentication
- **Telegram bot**: User authentication via Telegram ID
- **Web app**: JWT tokens for session management
- **API keys**: Stored in `.env`, rotated quarterly
- **OAuth 2.0**: For Jira and Google Docs integrations

### 7.3 Rate Limiting
- **Per user**: 10 requests/hour
- **Global**: 1,000 requests/hour
- **DDoS protection**: Cloudflare or similar CDN

---

## 8. Testing Strategy

### 8.1 Unit Tests
```python
def test_audio_download():
    """Test Telegram file download"""
    assert download_audio(mock_file_id) == "temp_file.ogg"

def test_transcription():
    """Test Whisper API call"""
    transcript = transcribe_audio("test_audio.mp3")
    assert len(transcript) > 0
    assert transcript.language == "ru"

def test_task_parsing():
    """Test GPT response parsing"""
    analysis = """
    ## Задачи
    1. Задача: Test task
       Дедлайн: 2025-11-10
       Ответственный: John
    """
    tasks = parse_tasks(analysis)
    assert len(tasks) == 1
    assert tasks[0]['description'] == "Test task"
```

### 8.2 Integration Tests
```python
def test_end_to_end_telegram():
    """Test full Telegram bot workflow"""
    # 1. Send audio to bot
    bot.send_voice(chat_id=TEST_USER_ID, voice=open("test.ogg", "rb"))
    
    # 2. Wait for processing
    time.sleep(120)
    
    # 3. Check response
    updates = bot.get_updates()
    assert "Summary:" in updates[-1].message.text
    assert "Задачи:" in updates[-1].message.text

def test_jira_integration():
    """Test Jira ticket creation"""
    issue = create_jira_issue({
        'description': 'Test task',
        'deadline': '2025-11-10',
        'assignee': 'testuser'
    })
    assert issue['key'].startswith('V2A-')
```

### 8.3 Load Testing
```python
# locust_test.py
from locust import HttpUser, task, between

class Voice2ActionUser(HttpUser):
    wait_time = between(5, 15)
    
    @task
    def upload_audio(self):
        with open("test_audio.mp3", "rb") as f:
            self.client.post("/api/process-audio", files={"audio": f})
    
    @task
    def poll_status(self):
        self.client.get(f"/api/status/{self.job_id}")
```

Run: `locust -f locust_test.py --users 100 --spawn-rate 10`

---

## 9. Deployment

### 9.1 Telegram Bot (Render.com)
```yaml
# render.yaml
services:
  - type: worker
    name: voice2action-bot
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python telegram-bot/bot.py
    envVars:
      - key: TELEGRAM_TOKEN
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: JIRA_URL
        sync: false
```

### 9.2 Web Application (Render.com)
```yaml
services:
  - type: web
    name: voice2action-web
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
```

### 9.3 Static Website (GitHub Pages)
```yaml
# .github/workflows/deploy.yml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./
```

---

## 10. Monitoring & Analytics

### 10.1 Metrics to Track
- **Processing time**: Average time per audio file
- **Success rate**: % of successful transcriptions
- **Error rate**: % of failed requests
- **User engagement**: Daily/weekly active users
- **API costs**: OpenAI usage (Whisper + GPT)

### 10.2 Logging
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('voice2action.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Log key events
logger.info(f"User {user_id} uploaded audio file {file_id}")
logger.info(f"Transcription completed in {elapsed_time:.2f}s")
logger.warning(f"Jira API rate limit hit, retrying in {backoff_time}s")
logger.error(f"Failed to process audio: {error_message}")
```

### 10.3 Alerts
- **Bot downtime**: Email/SMS if bot offline >5 minutes
- **High error rate**: Alert if >10% requests fail
- **API quota**: Warning at 80% of daily limit
- **Disk space**: Alert if <10% free space

---

## 11. Future Enhancements (Roadmap)

### Phase 1 (MVP) - Completed ✅
- Telegram bot with voice message support
- Whisper transcription
- GPT-4o-mini analysis
- Jira integration
- Static website

### Phase 2 (Q1 2026)
- Real-time processing during Zoom calls
- Confluence page creation
- Notion database sync
- Excel export (sales analytics)
- User dashboard (web app)

### Phase 3 (Q2 2026)
- Mobile app (iOS/Android)
- Multi-language support (EN, DE, FR)
- Custom AI prompts (user-defined)
- Team collaboration features
- Advanced analytics (sentiment analysis)

### Phase 4 (Q3 2026)
- On-premise deployment option
- Enterprise SSO integration
- Custom integrations (Slack, MS Teams)
- Voice command system ("Создай задачу для Алексея")
- AI training on company data

---

## 12. API Documentation

### 12.1 Telegram Bot Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message + instructions | `/start` |
| `/help` | List of features + examples | `/help` |
| `/feedback [text]` | Send feedback to developers | `/feedback Отличный бот!` |
| Voice message | Process audio → summary + tasks | [Send voice] |
| Audio file | Process uploaded file | [Upload MP3] |

#### POST /api/process-audio
**Upload audio file for processing**

**Request**:
```http
POST /api/process-audio
Content-Type: multipart/form-data

audio: [binary file]
analysis_type: meeting | sales | interview | custom  (optional)
custom_prompt: "..."  (if analysis_type=custom)

if analysis_type == 'sales':
    prompt = SALES_ANALYSIS_PROMPT.format(transcript=transcript.text)
elif analysis_type == 'interview':
    prompt = INTERVIEW_ANALYSIS_PROMPT.format(transcript=transcript.text)
elif analysis_type == 'custom':
    custom = context.user_data.get('custom_prompt', '')
    prompt = custom or DEFAULT_PROMPT.format(transcript=transcript.text)
else:
    prompt = MEETING_SUMMARY_PROMPT.format(transcript=transcript.text)

response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Ты ассистент для анализа встреч."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.3,
    max_tokens=1500
)
analysis = response.choices[0].message.content
```

**Response**:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "message": "Аудио принято в обработку"
}
```

#### GET /api/status/{job_id}
Check processing status

**Response (in progress)**:
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "Анализ текста...",
  "progress": 60,
  "stage": "GPT-4o-mini анализ",
  "eta_seconds": 25,
  "complete": false
}
```

**Response (when complete)**:
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "Готово",
  "progress": 100,
  "complete": true,
  "results": {
    "summary": "Обсуждение спринта 45. Согласовано 5 задач...",
    "tasks": [
      {
        "title": "Рефакторинг авторизации",
        "description": "Переписать JWT логику",
        "assignee": "Алексей",
        "deadline": "2025-11-08",
        "priority": "High"
      }
    ],
    "transcript": "Добрый день коллеги...",
    "duration_minutes": 47,
    "processing_time": 87.3
  }
}
```

---

#### POST /api/export

**Export results to selected destinations**  

*(Вызывается **после** получения `complete: true`)*

**Request**:

```json
{
  "job_id": "a1b2c3d4-...",
  "exports": ["excel", "word", "jira", "google_docs"]
}

```
**Response**:
```json
{
  "job_id": "a1b2c3d4-...",
  "exports": {
    "excel": {
      "status": "success",
      "download_url": "/download/excel/a1b2c3d4.xlsx",
      "filename": "Meeting_Analysis_2025-11-02.xlsx"
    },
    "word": {
      "status": "success",
      "download_url": "/download/word/a1b2c3d4.docx",
      "filename": "Protocol_2025-11-02.docx"
    },
    "jira": {
      "status": "success",
      "issues": [
        { "key": "V2A-101", "url": "https://jira.company.com/browse/V2A-101" },
        { "key": "V2A-102", "url": "https://jira.company.com/browse/V2A-102" }
      ]
    },
    "google_docs": {
      "status": "success",
      "doc_url": "https://docs.google.com/document/d/abc123/edit"
    }
  }
}
```
---

#### GET /download/excel/{job_id}

**Download generated Excel file**
→ Returns `.xlsx` file
→ `Content-Disposition: attachment; filename="Meeting_Analysis_*.xlsx"`
---

#### GET /download/word/{job_id}

**Download generated Word protocol**

→ Returns `.docx` file  

→ `Content-Disposition: attachment; filename="Protocol_*.docx"`
---

#### POST /api/feedback

**Submit user feedback**

**Request**:
```json
{
  "user_id": "telegram_12345",
  "job_id": "a1b2c3d4-...",
  "message": "Отличный сервис!",
  "rating": 5
}
```

**Response**:
```json
{
  "success": true,
  "message": "Спасибо за отзыв!"
}
```
---

## 13. Database Schema

### 13.1 PostgreSQL Tables
#### users
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP,
    subscription_tier VARCHAR(20) DEFAULT 'free',
    api_calls_used INT DEFAULT 0,
    api_calls_limit INT DEFAULT 3
);
```
#### audio_processing_jobs
```sql
CREATE TABLE audio_processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    file_path VARCHAR(500),
    file_size_bytes BIGINT,
    duration_seconds INT,
    status VARCHAR(50) DEFAULT 'queued',
    progress INT DEFAULT 0,
    analysis_type VARCHAR(50),  -- meeting, sales, interview, custom
    transcript TEXT,
    analysis JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    processing_time_seconds DECIMAL(10,2),
    api_cost_usd DECIMAL(10,4)
);
```
#### user_integrations
```sql
CREATE TABLE user_integrations (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    service VARCHAR(50) NOT NULL,
    credentials_encrypted TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, service)
);
```
#### exports
```sql
CREATE TABLE exports (
    id SERIAL PRIMARY KEY,
    job_id UUID REFERENCES audio_processing_jobs(id),
    export_type VARCHAR(50),
    file_path VARCHAR(500),
    external_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);
```
### 13.2 Sample Queries

#### Get user processing history
```sql
SELECT 
  j.id,
  j.created_at,
  j.status,
  j.duration_seconds,
  COUNT(ji.id) as tasks_created
FROM audio_processing_jobs j
LEFT JOIN jira_issues ji ON j.id = ji.job_id
WHERE j.user_id = $1
GROUP BY j.id
ORDER BY j.created_at DESC
LIMIT 10;
```

#### Calculate monthly API costs
```sql
SELECT 
  DATE_TRUNC('month', created_at) as month,
  COUNT(*) as total_jobs,
  SUM(duration_seconds) as total_audio_seconds,
  -- Estimate costs: Whisper $0.006/min, GPT-4o-mini $0.15/1M tokens
  SUM(duration_seconds / 60.0 * 0.006) + 
  COUNT(*) * 0.0005 as estimated_cost_usd
FROM audio_processing_jobs
WHERE status = 'completed'
GROUP BY month
ORDER BY month DESC;
```

---

## 14. Configuration Management

### 14.1 Environment Variables

Create `.env` file (NEVER commit to git):

```bash
# Telegram Bot
TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# OpenAI API
OPENAI_API_KEY=sk-proj-abc123...
OPENAI_ORG_ID=org-xyz789  # Optional

# Jira
JIRA_URL=https://your-company.atlassian.net
JIRA_EMAIL=bot@company.com
JIRA_API_TOKEN=ATATT3xFf...
JIRA_PROJECT_KEY=V2A

# Google Cloud (for Docs API)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
GOOGLE_DOCS_FOLDER_ID=1a2b3c4d5e6f7g8h

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/voice2action

# Application
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here

# Rate Limiting
MAX_REQUESTS_PER_HOUR=10
MAX_FILE_SIZE_MB=20
MAX_AUDIO_DURATION_MINUTES=60

# Monitoring
SENTRY_DSN=https://abc123@sentry.io/456789
UPTIMEROBOT_API_KEY=ur123456

# Feature Flags
ENABLE_GOOGLE_DOCS=true
ENABLE_SALES_ANALYSIS=true
ENABLE_REAL_TIME_PROCESSING=false
```

### 14.2 Configuration Class

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_ORG_ID = os.getenv('OPENAI_ORG_ID')
    
    # Jira
    JIRA_URL = os.getenv('JIRA_URL')
    JIRA_EMAIL = os.getenv('JIRA_EMAIL')
    JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
    JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'V2A')
    
    # Google
    GOOGLE_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    GOOGLE_DOCS_FOLDER = os.getenv('GOOGLE_DOCS_FOLDER_ID')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # App Settings
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    # Limits
    MAX_REQUESTS_PER_HOUR = int(os.getenv('MAX_REQUESTS_PER_HOUR', 10))
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE_MB', 20)) * 1024 * 1024
    MAX_DURATION = int(os.getenv('MAX_AUDIO_DURATION_MINUTES', 60)) * 60
    
    # Feature Flags
    ENABLE_GOOGLE_DOCS = os.getenv('ENABLE_GOOGLE_DOCS', 'true').lower() == 'true'
    ENABLE_SALES_ANALYSIS = os.getenv('ENABLE_SALES_ANALYSIS', 'true').lower() == 'true'
    
    @staticmethod
    def validate():
        """Validate required environment variables"""
        required = [
            'TELEGRAM_TOKEN',
            'OPENAI_API_KEY',
            'JIRA_URL',
            'JIRA_API_TOKEN',
            'DATABASE_URL'
        ]
        missing = [var for var in required if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

# Validate on import
Config.validate()
```
## 14.3 Encryption Utils
```python
# utils/encrypt.py
from cryptography.fernet import Fernet
import os
import json

key = os.getenv("ENCRYPTION_KEY").encode()
cipher = Fernet(key)

def encrypt(data: dict) -> str:
    return cipher.encrypt(json.dumps(data).encode()).decode()

def decrypt(token: str) -> dict:
    return json.loads(cipher.decrypt(token.encode()).decode()
```

## 15. Prompt Engineering Guide

### 15.1 Summary Prompt
```python
SUMMARY_PROMPT = """
Создай краткое резюме следующего текста встречи.

Требования:
- 3-5 предложений
- Выдели ключевые решения
- Укажи основные темы обсуждения
- Язык: русский

Текст встречи:
{transcript}

Резюме:
"""
```

### 15.2 Task Extraction Prompt
```python
TASK_EXTRACTION_PROMPT = """
Извлеки все задачи из текста встречи и структурируй их в следующем формате:

**Формат вывода:**
## Задачи
1. Задача: [Краткое описание задачи]
   Дедлайн: [Дата в формате YYYY-MM-DD или "Не указан"]
   Ответственный: [Имя человека или "Не указан"]
   Приоритет: [Высокий/Средний/Низкий или "Не указан"]

Правила:
- Извлекай только четко сформулированные задачи
- Если дедлайн не упомянут явно, пиши "Не указан"
- Если ответственный не назван, пиши "Не указан"
- Пронумеруй задачи по порядку

Текст встречи:
{transcript}

Задачи:
"""
```

### 15.3 Sales Call Analysis Prompt
```python
SALES_ANALYSIS_PROMPT = """
Проанализируй звонок продаж и предоставь детальный отчет.

**Анализ должен включать:**

1. **Слова-паразиты**: 
   - Количество ("эээ", "ммм", "типа", "как бы")
   - Примеры с таймкодами

2. **Паузы**:
   - Количество пауз >3 секунд
   - Контекст (неуверенность, обдумывание)

3. **Уверенность речи**:
   - Оценка: Высокая / Средняя / Низкая
   - Обоснование

4. **Структура разговора**:
   - Процент времени говорения (менеджер vs клиент)
   - Количество открытых вопросов
   - Наличие активного слушания

5. **Возражения клиента**:
   - Список возражений
   - Как менеджер обработал каждое

6. **Рекомендации**:
   - 3-5 конкретных советов для улучшения
   - Приоритетная область для развития

Транскрипт звонка:
{transcript}

Анализ:
"""
```

### 15.4 Meeting Protocol Prompt
```python
PROTOCOL_PROMPT = """
Создай официальный протокол встречи на основе транскрипта.

**Структура протокола:**

# Протокол встречи
**Дата**: {date}
**Участники**: {participants}

## 1. Повестка дня
[Список обсуждаемых тем]

## 2. Обсуждение
[Краткое описание каждой темы с ключевыми моментами]

## 3. Принятые решения
[Список всех решений с ответственными]

## 4. Действия
[Таблица: Задача | Ответственный | Срок]

## 5. Следующие шаги
[План на следующую встречу]

Транскрипт:
{transcript}

Протокол:
"""
```

### 15.5 Prompt Best Practices

1. **Be Specific**: Clear instructions, explicit output format
2. **Use Examples**: Show desired output structure
3. **Set Constraints**: "3-5 sentences", "Format: YYYY-MM-DD"
4. **Handle Edge Cases**: "If not mentioned, write 'Не указан'"
5. **Adjust Temperature**: 
   - 0.0-0.2 for structured extraction
   - 0.5-0.7 for creative summaries
6. **Test Iteratively**: Refine prompts based on output quality

---

## 16. Cost Estimation

### 16.1 API Costs per Request

| Service | Cost | Notes |
|---------|------|-------|
| **Whisper** | $0.006/min | 10-min audio = $0.06 |
| **GPT-4o-mini** | $0.15/1M input tokens | ~500 tokens = $0.00008 |
| **GPT-4o-mini** | $0.60/1M output tokens | ~800 tokens = $0.00048 |
| **Jira API** | Free | Included in Jira license |
| **Google Docs API** | Free | 60 requests/min limit |

**Example calculation (10-minute audio)**:
- Whisper: $0.06
- GPT-4o-mini: $0.00056
- **Total per request**: ~$0.061

**Monthly costs (1,000 requests)**:
- API costs: $61
- Render.com hosting: $7 (free tier)
- **Total**: ~$68/month

### 16.2 Revenue Model

| Plan | Price | Requests/month | Profit per user |
|------|-------|----------------|-----------------|
| **Free** | ₽0 | 3 | -₽12 (loss leader) |
| **Team** | ₽990 | 50 | ₽687 (₽990 - ₽303 costs) |
| **Business** | ₽3990 | Unlimited | ₽3000+ (at scale) |

**Break-even**: ~15 Team subscribers

---

## 17. Compliance & Legal

### 17.1 GDPR Compliance

**User Rights**:
- Right to access: Export all user data via `/export` command
- Right to deletion: `/delete_data` command (permanent)
- Right to portability: JSON export of all processing history
- Consent: Explicit opt-in on first use

**Implementation**:
```python
@app.command("/export_data")
async def export_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # Fetch all data
    data = {
        "user": get_user_info(user_id),
        "jobs": get_processing_history(user_id),
        "feedback": get_user_feedback(user_id)
    }
    
    # Send as JSON file
    json_file = json.dumps(data, indent=2, ensure_ascii=False)
    await update.message.reply_document(
        document=json_file.encode(),
        filename=f"voice2action_data_{user_id}.json"
    )

@app.command("/delete_data")
async def delete_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # Confirm deletion
    keyboard = [
        [InlineKeyboardButton("Да, удалить", callback_data="confirm_delete")],
        [InlineKeyboardButton("Отмена", callback_data="cancel_delete")]
    ]
    
    await update.message.reply_text(
        "⚠️ Все ваши данные будут удалены безвозвратно. Продолжить?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
```

### 17.2 Terms of Service (ToS)

**Key clauses**:
1. Audio files deleted after 24 hours
2. No guarantees on transcription accuracy
3. User responsible for content legality
4. API rate limits enforced
5. Service may be suspended without notice

### 17.3 Privacy Policy

**Data collected**:
- Telegram user ID (required)
- Audio files (temporary, auto-deleted)
- Processing metadata (timestamps, status)
- Feedback messages (optional)

**Data NOT collected**:
- Phone numbers
- Email addresses (unless provided)
- Location data
- Payment information (handled by payment processor)

**Third-party sharing**:
- OpenAI: Audio transcription (covered by their DPA)
- Jira: Task metadata only
- Google: Document creation (user-authorized)

---

## 18. Troubleshooting Guide

### 18.1 Common Issues

#### Bot doesn't respond
**Symptoms**: User sends message, no reply  
**Causes**:
1. Bot token expired/invalid
2. Render.com worker sleeping (free tier)
3. Network connectivity issue

**Solutions**:
```bash
# Check bot status
curl https://api.telegram.org/bot<TOKEN>/getMe

# Restart worker (Render.com)
render restart voice2action-bot

# Check logs
render logs voice2action-bot --tail 100
```

#### Transcription fails
**Symptoms**: "Не удалось распознать аудио"  
**Causes**:
1. Audio too short (<1 second)
2. Corrupted file
3. Whisper API timeout

**Solutions**:
```python
# Add validation
if audio_duration < 1.0:
    await message.reply_text("Аудио слишком короткое. Минимум 1 секунда.")
    return

# Increase timeout
transcript = await asyncio.wait_for(
    transcribe_audio(file_path),
    timeout=180  # 3 minutes
)
```

#### Jira tickets not created
**Symptoms**: Summary received, but no Jira link  
**Causes**:
1. Invalid Jira credentials
2. Project doesn't exist
3. User lacks permissions

**Solutions**:
```python
# Test Jira connection
try:
    jira.projects()
    logger.info("Jira connection successful")
except Exception as e:
    logger.error(f"Jira auth failed: {e}")
    await message.reply_text(
        "⚠️ Не удалось создать задачи в Jira. Отправлен email администратору."
    )
```

### 18.2 Debug Mode

Enable verbose logging:

```python
# .env
DEBUG=true
LOG_LEVEL=DEBUG

# In code
if Config.DEBUG:
    logger.debug(f"Received audio: {file.file_id}")
    logger.debug(f"File size: {file.file_size} bytes")
    logger.debug(f"Transcript length: {len(transcript)} chars")
    logger.debug(f"GPT response: {response[:200]}...")
```

---

## 19. Migration Guide (v1.0 → v2.0)

### 19.1 Breaking Changes
- Database schema updated (new columns)
- API response format changed (nested JSON)
- Prompt templates restructured

### 19.2 Migration Steps

```sql
-- Add new columns
ALTER TABLE audio_processing_jobs 
ADD COLUMN analysis_version VARCHAR(10) DEFAULT 'v1.0',
ADD COLUMN processing_time_seconds FLOAT,
ADD COLUMN api_cost_usd DECIMAL(10,4);

-- Migrate old data
UPDATE audio_processing_jobs 
SET analysis_version = 'v1.0'
WHERE analysis_version IS NULL;

-- Create new index
CREATE INDEX idx_jobs_version ON audio_processing_jobs(analysis_version);
```

### 19.3 Rollback Plan

```bash
# Tag current version
git tag v1.0.0

# If v2.0 fails, revert
git checkout v1.0.0
render deploy

# Restore database backup
pg_restore --clean --if-exists -d voice2action backup_v1.sql
```

---

## 20. Success Metrics (KPIs)

### 20.1 Product Metrics
- **Daily Active Users (DAU)**: Target 100+ by month 3
- **Processing success rate**: >95%
- **Average processing time**: <2 minutes
- **User retention**: 60% month-over-month

### 20.2 Technical Metrics
- **API uptime**: 99.5%
- **Average response time**: <3 seconds
- **Error rate**: <2%
- **Cost per request**: <$0.10

### 20.3 Business Metrics
- **Monthly Recurring Revenue (MRR)**: ₽50,000 by month 6
- **Customer Acquisition Cost (CAC)**: <₽500
- **Lifetime Value (LTV)**: >₽5,000
- **Churn rate**: <10%

### 20.4 Dashboard Queries

```sql
-- DAU
SELECT DATE(created_at) as date, COUNT(DISTINCT user_id) as dau
FROM audio_processing_jobs
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY date
ORDER BY date;

-- Success rate
SELECT 
  COUNT(*) FILTER (WHERE status = 'completed') * 100.0 / COUNT(*) as success_rate
FROM audio_processing_jobs
WHERE created_at >= NOW() - INTERVAL '7 days';

-- Average processing time
SELECT AVG(processing_time_seconds) as avg_time
FROM audio_processing_jobs
WHERE status = 'completed'
  AND created_at >= NOW() - INTERVAL '7 days';
```

---

## 21. Glossary

| Term | Definition |
|------|------------|
| **Transcription** | Converting audio to text using Whisper |
| **Analysis** | Extracting summary + tasks via GPT-4o-mini |
| **Job** | Single audio processing request |
| **Pipeline** | End-to-end workflow (upload → response) |
| **Rate limiting** | Restricting requests per user/time |
| **Webhook** | HTTP callback for async notifications |
| **Polling** | Repeatedly checking job status |
| **Idempotency** | Same request produces same result |

---

## Appendix A: Sample Outputs

### A.1 Telegram Bot Response
```
✅ Обработка завершена!

📝 Summary:
Обсуждение спринта 45. Команда согласовала 5 задач на неделю. Основной фокус - рефакторинг модуля авторизации и новый API endpoint для экспорта отчетов.

📋 Задачи:
1. Рефакторинг модуля авторизации
   📅 Дедлайн: 2025-11-08
   👤 Ответственный: Алексей

2. Создать API для экспорта отчетов
   📅 Дедлайн: 2025-11-10
   👤 Ответственный: Мария

🔗 Jira:
V2A-101 | V2A-102

📄 Google Doc:
https://docs.google.com/document/d/abc123/edit

⏱ Время обработки: 47.3 сек
```

### A.2 Web App Results Display
```html
<div class="results-card">
  <h2 class="success-header">✅ Обработка завершена</h2>
  
  <section class="summary-box">
    <h3>📝 Summary</h3>
    <p>Обсуждение спринта 45. Команда согласовала...</p>
  </section>
  
  <section class="tasks-box">
    <h3>📋 Задачи</h3>
    <div class="task-card">
      <strong>Рефакторинг модуля авторизации</strong>
      <div class="task-meta">
        <span class="deadline">📅 2025-11-08</span>
        <span class="assignee">👤 Алексей</span>
      </div>
    </div>
  </section>
  
  <section class="links-box">
    <h3>🔗 Ссылки</h3>
    <a href="https://jira.com/V2A-101" target="_blank" class="jira-badge">
      V2A-101
    </a>
    <a href="https://docs.google.com/..." target="_blank" class="doc-link">
      📄 Google Doc
    </a>
  </section>
</div>
```

---

## Appendix B: Dependencies

### B.1 Python Requirements
```txt
# requirements.txt
python-telegram-bot==20.7
openai==1.3.0
python-dotenv==1.0.0
atlassian-python-api==3.41.0
fastapi==0.109.0
uvicorn[standard]==0.27.0
psycopg2-binary==2.9.9
sqlalchemy==2.0.25
pydub==0.25.1
google-api-python-client==2.116.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
pytest==8.0.0
pytest-asyncio==0.23.4
pytest-cov==4.1.0
locust==2.20.1
sentry-sdk==1.40.0
openpyxl==3.1.2
python-docx==1.1.0
cryptography==42.0.5
```

---

## Appendix C: File Structure

```
voice2action-site/
├── telegram-bot/
│   ├── bot.py                    # Main bot logic
│   ├── handlers/
│   │   ├── audio_handler.py
│   │   ├── command_handler.py
│   │   └── feedback_handler.py
│   ├── services/
│   │   ├── transcription.py      # Whisper API
│   │   ├── analysis.py           # GPT-4o-mini
│   │   ├── jira_service.py
│   │   └── gdocs_service.py
│   └── utils/
│       ├── file_converter.py
│       ├── validators.py
│       └── formatters.py
│
├── backend/
│   ├── main.py                   # FastAPI app
│   ├── api/
│   │   ├── routes.py
│   │   └── websockets.py
│   ├── models/
│   │   ├── database.py
│   │   └── schemas.py
│   └── tasks/
│       └── processing_queue.py
│
├── frontend/
│   ├── index.html
│   ├── app.html                  # Upload interface
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── main.js
│       └── upload.js
│
├── tests/
│   ├── test_bot.py
│   ├── test_transcription.py
│   ├── test_analysis.py
│   └── test_integrations.py
│
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── constitution.md
```

---

**Document Version**: 1.5  
**Last Updated**: 2025-11-02  
**Author**: Voice2Action Team  
**Status**: Enhanced MVP – Ready for Scale