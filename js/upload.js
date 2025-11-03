// Backend URL (пока локально, потом заменишь на Render)
const API_URL = "http://localhost:8000";

async function uploadAudio() {
  const fileInput = document.getElementById('audioFile');
  const statusDiv = document.getElementById('uploadStatus');
  const resultDiv = document.getElementById('uploadResult');

  // Проверка файла
  if (!fileInput.files || !fileInput.files[0]) {
    statusDiv.innerHTML = '<p class="error">⚠️ Выбери аудиофайл!</p>';
    return;
  }

  const file = fileInput.files[0];

  // Проверка размера (макс 25 МБ)
  if (file.size > 25 * 1024 * 1024) {
    statusDiv.innerHTML = '<p class="error">⚠️ Файл слишком большой (макс 25 МБ)</p>';
    return;
  }

  // Подготовка
  const formData = new FormData();
  formData.append('file', file);

  // Загрузка
  statusDiv.innerHTML = '<p class="loading">⏳ Загружаю и транскрибирую...</p>';
  resultDiv.innerHTML = '';

  try {
    const response = await fetch(`${API_URL}/api/process-audio`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Ошибка ${response.status}`);
    }

    const data = await response.json();

    // Успех!
    statusDiv.innerHTML = '<p class="success">✅ Готово!</p>';
    resultDiv.innerHTML = `
      <div class="result-card">
        <h3>📄 Транскрипт</h3>
        <p>${data.transcript}</p>
      </div>

      <div class="result-card">
        <h3>📊 Анализ</h3>
        <pre>${data.analysis}</pre>
      </div>

      <div class="result-links">
        <a href="${data.google_doc}" target="_blank" class="btn secondary">📝 Открыть Google Doc</a>
        <a href="${data.google_sheet}" target="_blank" class="btn secondary">📈 Открыть Google Sheet</a>
      </div>
    `;

  } catch (error) {
    statusDiv.innerHTML = `<p class="error">❌ Ошибка: ${error.message}</p>`;
    console.error(error);
  }
}