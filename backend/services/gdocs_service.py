import os
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# --- SCOPES ---
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

# --- Путь к credentials.json ---
CREDENTIALS_FILE = 'credentials.json'  # В корне проекта

class GoogleDocsService:
    def __init__(self):
        self.docs_service = None
        self.sheets_service = None
        self.drive_service = None
        self._authenticate()

    def _authenticate(self):
        """OAuth 2.0 авторизация через браузер"""
        if not os.path.exists(CREDENTIALS_FILE):
            raise FileNotFoundError(f"Файл {CREDENTIALS_FILE} не найден в корне проекта!")

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=8000)  # ← ИЗМЕНИЛ НА 8080

        self.docs_service = build('docs', 'v1', credentials=creds)
        self.sheets_service = build('sheets', 'v4', credentials=creds)
        self.drive_service = build('drive', 'v3', credentials=creds)
        logger.info("Google API подключён через OAuth")

    def create_doc(self, title: str, content: str) -> str:
        """Создаёт Google Doc"""
        try:
            doc = self.docs_service.documents().create(body={'title': title}).execute()
            doc_id = doc['documentId']

            requests = [{
                'insertText': {
                    'location': {'index': 1},
                    'text': content
                }
            }]
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, body={'requests': requests}
            ).execute()

            # Делаем доступным
            self.drive_service.permissions().create(
                fileId=doc_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            url = f"https://docs.google.com/document/d/{doc_id}/edit"
            logger.info(f"Google Doc создан: {url}")
            return url
        except Exception as e:
            logger.error(f"Ошибка создания Doc: {e}")
            raise

    def create_sheet(self, title: str, tasks: list) -> str:
        """Создаёт Google Sheet с задачами"""
        try:
            spreadsheet = {
                'properties': {'title': title},
                'sheets': [{'properties': {'title': 'Задачи'}}]
            }
            sheet = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
            sheet_id = sheet['spreadsheetId']

            # Заголовки
            values = [['Задача', 'Дедлайн', 'Ответственный']]
            for task in tasks:
                values.append([
                    task.get('description', ''),
                    task.get('deadline', '—'),
                    task.get('assignee', '—')
                ])

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='Задачи!A1',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()

            # Доступ
            self.drive_service.permissions().create(
                fileId=sheet_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
            logger.info(f"Google Sheet создан: {url}")
            return url
        except Exception as e:
            logger.error(f"Ошибка создания Sheet: {e}")
            raise

# --- ТЕСТ ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        service = GoogleDocsService()
        doc_url = service.create_doc(
            "Тест Voice2Action",
            "Привет! Это тест документа, созданного AI."
        )
        print(f"Документ: {doc_url}")

        sheet_url = service.create_sheet("Тест Задачи", [
            {"description": "Сделать презентацию", "deadline": "2025-11-05", "assignee": "Антон"}
        ])
        print(f"Таблица: {sheet_url}")
    except Exception as e:
        print(f"Ошибка: {e}")