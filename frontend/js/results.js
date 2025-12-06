// НОВЫЙ upload.js — polling + красивые результаты
const API_URL = "http://localhost:8000";

async function uploadAudio() {
  const fileInput = document.getElementById('audioFile');
  const statusDiv = document.getElementById('uploadStatus');
  const progressBar = document.getElementById('progressFill');
  const resultDiv = document.getElementById('uploadResult');

  const file = fileInput.files[0];
  if (!file) return showStatus('⚠️ Выбери аудиофайл!', 'error');

  // 1. Загрузка
  showStatus('⏳ Загружаю аудио...', 'loading');
  const formData = new FormData();
  formData.append('audio', file);  // ИСПРАВЛЕНО: 'audio', не 'file'

  try {
    const response = await fetch(`${API_URL}/api/process-audio`, {
      method: 'POST', body: formData
    });
    const data = await response.json();
    const jobId = data.job_id;

    // 2. Polling статуса
    await pollJobStatus(jobId, statusDiv, progressBar);

    // 3. Получить финальные результаты
    const results = await fetchResults(jobId);
    showResults(results, resultDiv);

  } catch (error) {
    showStatus(`❌ Ошибка: ${error.message}`, 'error');
  }
}

async function pollJobStatus(jobId, statusDiv, progressBar) {
  const maxAttempts = 60; // 2 минуты
  let attempts = 0;

  while (attempts < maxAttempts) {
    attempts++;
    const response = await fetch(`${API_URL}/api/jobs/${jobId}`);
    const job = await response.json();

    updateProgress(job.progress || 0, job.status, statusDiv, progressBar);

    if (job.status === 'completed') return job;
    if (job.status === 'failed') throw new Error(job.error);

    await new Promise(r => setTimeout(r, 2000)); // 2 сек
  }
  throw new Error('Обработка заняла слишком много времени');
}
