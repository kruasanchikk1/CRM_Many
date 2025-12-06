// upload.js - НОВАЯ ВЕРСИЯ для работы с API
const API_URL = "https://voice2action-api-vq9x.onrender.com";

let currentFile = null;
let currentJobId = null;
let lastProgressValue = 0;

const STATUS_PROGRESS_MAP = {
  queued: 5,
  uploading: 12,
  transcribing: 35,
  processing: 60,
  analyzing: 80,
  exporting: 90,
  completed: 100,
  failed: 100
};

document.addEventListener('DOMContentLoaded', function() {
  initUploadApp();
});

function initUploadApp() {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('audioFile');
  const analyzeButton = document.getElementById('analyzeButton');
  const analysisTypeSection = document.getElementById('analysisTypeSection');
  const analyzeButtonContainer = document.getElementById('analyzeButtonContainer');
  const resultActions = document.getElementById('resultActions');

  // 🖱️ Drag & Drop
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(event => {
    dropZone.addEventListener(event, e => e.preventDefault());
  });

  dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

  dropZone.addEventListener('drop', e => {
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  });

  dropZone.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', e => {
    const file = e.target.files[0];
    if (file) handleFileSelect(file);
  });

  // Кнопка анализа
  analyzeButton.addEventListener('click', () => {
    if (currentFile) {
      analyzeAudio(currentFile);
    }
  });

  window.resetForm = function() {
    currentFile = null;
    currentJobId = null;
    lastProgressValue = 0;
    fileInput.value = '';
    document.getElementById('uploadResult').style.display = 'none';
    document.getElementById('progressContainer').style.display = 'none';
    const statusEl = document.getElementById('uploadStatus');
    statusEl.style.display = 'none';
    statusEl.innerHTML = '';
    if (resultActions) resultActions.style.display = 'none';
    analysisTypeSection.style.display = 'none';
    analyzeButtonContainer.style.display = 'none';
    updateProgress(0, 'Ждём загрузку аудио...');
    resetDropZone();
  };

  function resetDropZone() {
    dropZone.innerHTML = `
      <div class="upload-icon">📁</div>
      <h3>Перетащи аудиофайл сюда</h3>
      <p>или кликни чтобы выбрать</p>
      <input type="file" id="audioFile" accept="audio/*,.mp3,.wav,.ogg,.m4a" hidden>
      <div class="upload-meta">
        <span>MP3 · WAV · OGG · M4A</span>
        <span>до 25 МБ</span>
      </div>
    `;
    // Переподключаем обработчики
    const newFileInput = document.getElementById('audioFile');
    newFileInput.addEventListener('change', e => {
      const file = e.target.files[0];
      if (file) handleFileSelect(file);
    });
    dropZone.addEventListener('click', () => newFileInput.click());
  }
}

function handleFileSelect(file) {
  // ✅ Валидация
  if (!file) return;
  lastProgressValue = 0;

  const validTypes = ['audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'audio/mp3'];
  const validExtensions = ['.mp3', '.wav', '.ogg', '.m4a'];
  const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
  
  if (!validTypes.includes(file.type) && !validExtensions.includes(fileExtension)) {
    showStatus('❌ Только MP3/OGG/WAV/M4A', 'error');
    return;
  }

  if (file.size > 25 * 1024 * 1024) {
    showStatus('❌ Файл > 25 МБ', 'error');
    return;
  }

  // Сохраняем файл
  currentFile = file;

  // Показываем информацию о файле
  const dropZone = document.getElementById('dropZone');
  dropZone.innerHTML = `
    <div class="upload-icon">✅</div>
    <h3>Файл выбран: ${file.name}</h3>
    <p style="color: #666; font-size: 0.9em;">Размер: ${(file.size / 1024 / 1024).toFixed(2)} МБ</p>
  `;

  // Показываем выбор типа анализа и кнопку
  document.getElementById('analysisTypeSection').style.display = 'block';
  document.getElementById('analyzeButtonContainer').style.display = 'block';
  
  showStatus('✅ Файл готов к анализу. Выбери тип анализа и нажми "Анализировать"', 'success');
}

async function analyzeAudio(file) {
  const resultDiv = document.getElementById('uploadResult');
  const progressContainer = document.getElementById('progressContainer');
  const resultActions = document.getElementById('resultActions');

  // Получаем выбранный тип анализа
  const analysisType = document.querySelector('input[name="analysis"]:checked')?.value || 'auto';

  // Скрываем выбор типа анализа и кнопку
  document.getElementById('analysisTypeSection').style.display = 'none';
  document.getElementById('analyzeButtonContainer').style.display = 'none';

  // Показываем прогресс
  progressContainer.style.display = 'block';
  resultDiv.style.display = 'none';
  if (resultActions) resultActions.style.display = 'none';
  showStatus('📤 Загружаю аудио на сервер...', 'loading');
  updateProgress(10, 'Отправка файла...');

  try {
    // 1. ЗАГРУЗКА ФАЙЛА
    const formData = new FormData();
    formData.append('audio', file); // FastAPI ожидает поле 'audio'
    formData.append('analysis_type', analysisType);

    const response = await fetch(`${API_URL}/api/process-audio`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const serverMessage = normalizeServerError(errorData, response.status);
      throw new Error(serverMessage);
    }

    const data = await response.json();
    currentJobId = data.job_id;

    showStatus(`✅ Job ${currentJobId.slice(0, 8)}... запущен`, 'success');
    updateProgress(20, 'Транскрипция (Yandex SpeechKit)...');

    // 2. POLLING СТАТУСА
    const jobData = await pollJobStatus(currentJobId);

    // 3. РЕЗУЛЬТАТЫ
    updateProgress(100, 'Готово!');
    showStatus('🎉 Обработка завершена!', 'success');
    showResults(jobData, resultDiv);

  } catch (error) {
    showStatus(`❌ Ошибка: ${error.message}`, 'error');
    console.error('Upload error:', error);
    // Показываем обратно выбор типа анализа при ошибке
    document.getElementById('analysisTypeSection').style.display = 'block';
    document.getElementById('analyzeButtonContainer').style.display = 'block';
  }
}

async function pollJobStatus(jobId) {
  const maxAttempts = 90; // 3 минуты (90 * 2 сек)
  let attempts = 0;

  while (attempts < maxAttempts) {
    attempts++;

    try {
      const response = await fetch(`${API_URL}/api/jobs/${jobId}`);
      if (!response.ok) {
        // Пробуем альтернативный эндпоинт
        const altResponse = await fetch(`${API_URL}/api/status/${jobId}`);
        if (!altResponse.ok) throw new Error('Job не найден');
        const job = await altResponse.json();
        return handleJobResponse(job);
      }

      const job = await response.json();
      const result = handleJobResponse(job);
      if (result) return result;

    } catch (error) {
      console.warn(`Polling ${attempts}:`, error);
      if (attempts === 1) {
        // Первая попытка - пробуем альтернативный эндпоинт
        try {
          const altResponse = await fetch(`${API_URL}/api/status/${jobId}`);
          if (altResponse.ok) {
            const job = await altResponse.json();
            const result = handleJobResponse(job);
            if (result) return result;
          }
        } catch (e) {
          // Игнорируем
        }
      }
    }

    await new Promise(r => setTimeout(r, 2000)); // 2 сек
  }

  throw new Error('⏰ Таймаут (3 мин). Проверь статус вручную через Swagger UI');
}

function handleJobResponse(job) {
  // 🔥 LIVE PROGRESS
  const rawProgress = typeof job.progress === 'number'
    ? job.progress
    : deriveProgressFromStatus(job.status);
  const progress = job.status === 'completed' ? 100 : rawProgress;
  const status = job.status || 'processing';
  const statusText = getStatusText(status, progress);
  
  updateProgress(progress, statusText);

  if (status === 'completed') {
    return job;
  }
  if (status === 'failed') {
    throw new Error(job.error || 'Серверная ошибка');
  }

  return null; // Продолжаем polling
}

function getStatusText(status, progress) {
  if (status === 'processing') {
    if (progress < 30) return 'Транскрипция (Yandex SpeechKit)...';
    if (progress < 70) return 'Анализ (YandexGPT)...';
    if (progress < 90) return 'Создание документов...';
    return 'Завершение...';
  }
  return status;
}

function showResults(job, resultDiv) {
  resultDiv.style.display = 'block';
  resultDiv.scrollIntoView({ behavior: 'smooth' });
  const resultActions = document.getElementById('resultActions');
  if (resultActions) resultActions.style.display = 'flex';

  const fallbackTranscript = job.transcript?.text || job.transcript_text || job.results?.transcript || '';

  // 📋 SUMMARY
  const summary = job.analysis?.summary ||
                  job.results?.summary ||
                  (fallbackTranscript ? `${fallbackTranscript.slice(0, 500)}...` : 'Резюме недоступно');
  document.getElementById('summaryContent').innerHTML = `<p style="white-space: pre-wrap; line-height: 1.6;">${escapeHtml(summary)}</p>`;

  // ✅ TASKS
  const tasks = job.analysis?.tasks || job.results?.tasks || [];
  const tasksContent = document.getElementById('tasksContent');

  if (tasks.length) {
    tasksContent.innerHTML = tasks.map(task => {
      const taskObj = typeof task === 'string' ? { description: task } : task;
      const desc = taskObj.description || taskObj.task || 'Без описания';
      const deadline = taskObj.deadline || taskObj.due_date;
      const assignee = taskObj.assignee || taskObj.assigned_to;
      const priority = taskObj.priority;
      
      return `
        <div class="task-item">
          <strong>${escapeHtml(desc)}</strong>
          ${deadline ? `<br><small>📅 ${escapeHtml(deadline)}</small>` : ''}
          ${assignee ? `<br><small>👤 ${escapeHtml(assignee)}</small>` : ''}
          ${priority ? `<br><small>🔥 ${escapeHtml(priority)}</small>` : ''}
        </div>
      `;
    }).join('');
  } else {
    tasksContent.innerHTML = '<p style="color: #666;">Задачи не найдены</p>';
  }

  // 💡 KEY POINTS
  renderListSection(job.analysis?.key_points || job.results?.key_points, 'insightsContent', 'Ключевые моменты появятся после анализа.');

  // 🧠 DECISIONS
  renderListSection(job.analysis?.decisions || job.results?.decisions, 'decisionsContent', 'Решения не найдены или не были озвучены.');

  // 🔗 DOCS
  const docsContent = document.getElementById('docsContent');
  const links = [];

  if (job.analysis?.doc_url) {
    links.push(`<a href="${job.analysis.doc_url}" target="_blank" class="btn secondary">📝 Google Doc</a>`);
  }
  if (job.analysis?.sheet_url && job.analysis.sheet_url !== 'Нет задач для экспорта') {
    links.push(`<a href="${job.analysis.sheet_url}" target="_blank" class="btn secondary">📊 Google Sheet</a>`);
  }

  docsContent.innerHTML = links.length ? links.join('') : '<p style="color: #666;">Документы создаются автоматически</p>';

  // 🆔 JOB ID
  if (currentJobId) {
    const jobIdEl = document.getElementById('jobIdDisplay');
    const copyBtn = document.getElementById('copyJobId');
    jobIdEl.textContent = currentJobId;
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(currentJobId).then(() => {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = '✅ Скопировано!';
        setTimeout(() => {
          copyBtn.textContent = originalText;
        }, 2000);
      });
    };
  }
}

function showStatus(message, type) {
  const statusDiv = document.getElementById('uploadStatus');
  if (!statusDiv) return;

  const icons = {
    loading: '⏳',
    success: '✅',
    error: '⚠️'
  };

  statusDiv.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><div>${message}</div>`;
  statusDiv.className = `status-message status-${type}`;
  statusDiv.style.display = 'flex';
}

function updateProgress(percent, text) {
  const progressFill = document.getElementById('progressFill');
  const progressTextEl = document.getElementById('progressText');
  const progressPercentEl = document.getElementById('progressPercent');
  const clamped = Math.min(100, Math.max(0, percent));
  lastProgressValue = Math.max(lastProgressValue, clamped);

  if (progressFill) progressFill.style.width = `${lastProgressValue}%`;
  if (progressPercentEl) progressPercentEl.textContent = `${Math.round(lastProgressValue)}%`;
  if (progressTextEl && text) progressTextEl.textContent = text;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function renderListSection(items = [], targetId, emptyText) {
  const target = document.getElementById(targetId);
  if (!target) return;

  if (items && items.length) {
    target.innerHTML = `
      <ul class="${targetId === 'insightsContent' ? 'insights-list' : 'decisions-list'}">
        ${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
      </ul>
    `;
  } else {
    target.innerHTML = `<p style="color:#666;">${emptyText}</p>`;
  }
}

function deriveProgressFromStatus(status = '') {
  return STATUS_PROGRESS_MAP[status] ?? lastProgressValue;
}

function normalizeServerError(payload, statusCode) {
  if (!payload) return `HTTP ${statusCode}`;
  const detail = payload.detail ?? payload.message ?? payload.error;

  if (!detail) {
    try {
      return JSON.stringify(payload);
    } catch (e) {
      return `HTTP ${statusCode}`;
    }
  }

  if (Array.isArray(detail)) {
    return detail
      .map(item => item.msg || item.message || JSON.stringify(item))
      .join('; ');
  }

  if (typeof detail === 'object') {
    try {
      return JSON.stringify(detail);
    } catch (e) {
      return String(detail);
    }
  }

  return detail;
}
