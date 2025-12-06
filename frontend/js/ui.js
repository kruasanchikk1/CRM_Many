// 🎨 UI УТИЛИТЫ + DRAG&DROP
document.addEventListener('DOMContentLoaded', initUI);

function initUI() {
  // 🔗 ЭЛЕМЕНТЫ
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('audioFile');
  const selectBtn = document.getElementById('selectFileBtn');
  const settingsSection = document.getElementById('settingsSection');

  let selectedFile = null;
  let jobId = null;

  // 🖱️ FILE SELECT
  selectBtn.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', handleFileSelect);

  // 🖱️ DRAG & DROP
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(event => {
    dropZone.addEventListener(event, e => e.preventDefault());
  });

  dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

  dropZone.addEventListener('drop', e => {
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    handleFileSelect({ target: { files: [file] } });
  });

  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    // ✅ ВАЛИДАЦИЯ
    if (!['audio/mpeg','audio/ogg','audio/wav','audio/mp4'].includes(file.type)) {
      showNotification('❌ Только MP3/OGG/WAV/M4A', 'error');
      return;
    }

    if (file.size > 25*1024*1024) {
      showNotification('❌ Максимум 25 МБ', 'error');
      return;
    }

    selectedFile = file;
    updateDropZone(file.name, formatSize(file.size));
    settingsSection.classList.remove('hidden');
  }

  function updateDropZone(filename, filesize) {
    dropZone.innerHTML = `
      <div class="upload-icon">✅</div>
      <h3>${filename}</h3>
      <p>${filesize}</p>
      <button class="btn secondary" onclick="ui.resetFile()">← Другой файл</button>
    `;
  }

  // 🌈 УВЕДОМЛЕНИЯ
  function showNotification(message, type = 'info') {
    // TODO: toast notification
    alert(message);
  }

  // 🔄 RESET
  window.ui = {
    resetFile() {
      selectedFile = null;
      fileInput.value = '';
      initDropZone();
      settingsSection.classList.add('hidden');
    },

    getSelectedFile() { return selectedFile; },
    getJobId() { return jobId; },
    setJobId(id) { jobId = id; }
  };

  function initDropZone() {
    dropZone.innerHTML = `
      <div class="upload-icon">📁</div>
      <h3>Перетащи аудиофайл сюда</h3>
      <p>или</p>
      <input type="file" id="audioFile" accept="audio/*" hidden>
      <button class="btn primary-btn" id="selectFileBtn">Выбрать файл</button>
      <p class="file-hint">MP3, OGG, WAV, M4A (до 25 МБ)</p>
    `;
  }

  function formatSize(bytes) {
    return (bytes / 1024 / 1024).toFixed(1) + ' МБ';
  }
}
