import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]


class GoogleDocsService:
    def __init__(self):
        self.docs_service = None
        self.sheets_service = None
        self.drive_service = None
        self._authenticate_oauth()

    def _authenticate_oauth(self):
        """OAuth 2.0 аутентификация (работает с 2FA)"""
        creds = None

        # Файл для сохранения токена
        token_file = 'token.pickle'

        # Загружаем сохранённый токен
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)

        # Если нет валидных креденциалов
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)

                # ⭐ ВАЖНО! Используем порт, указанный в redirect_uris
                creds = flow.run_local_server(
                    port=8000,  # или 8080
                    open_browser=True,
                    success_message='✅ Авторизация успешна! Закройте это окно.'
                )

            # Сохраняем токен для следующего раза
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)

        self.docs_service = build('docs', 'v1', credentials=creds)
        self.sheets_service = build('sheets', 'v4', credentials=creds)
        self.drive_service = build('drive', 'v3', credentials=creds)
        logger.info("✅ Google API подключён через OAuth 2.0")

    def create_doc(self, title: str, content: str) -> str:
        """Создаёт Google Doc"""
        try:
            doc = self.docs_service.documents().create(
                body={'title': title}
            ).execute()

            doc_id = doc['documentId']

            requests = [{
                'insertText': {
                    'location': {'index': 1},
                    'text': content
                }
            }]

            self.docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            self.drive_service.permissions().create(
                fileId=doc_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            url = f"https://docs.google.com/document/d/{doc_id}/edit"
            logger.info(f"✅ Google Doc создан: {url}")
            return url

        except HttpError as e:
            logger.error(f"❌ Ошибка создания Google Doc: {e}")
            raise

        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при создании Doc: {e}")
            raise

    def create_sheet(self, title: str, tasks: list) -> str:
        """Создаёт Google Sheet с задачами"""
        try:
            spreadsheet = {
                'properties': {'title': title},
                'sheets': [{'properties': {'title': 'Задачи'}}]
            }

            sheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet
            ).execute()

            sheet_id = sheet['spreadsheetId']

            values = [['Задача', 'Дедлайн', 'Ответственный', 'Приоритет']]

            for task in tasks:
                values.append([
                    task.get('description', ''),
                    task.get('deadline', 'Не указан'),
                    task.get('assignee', 'Не указан'),
                    task.get('priority', 'Medium')
                ])

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='Задачи!A1',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()

            self.drive_service.permissions().create(
                fileId=sheet_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
            logger.info(f"✅ Google Sheet создан: {url}")
            return url

        except HttpError as e:
            logger.error(f"❌ Ошибка создания Google Sheet: {e}")
            raise

        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при создании Sheet: {e}")
            raise


async def add_to_google_docs(transcript: str, analysis: dict) -> dict:
    """Создаёт Google Docs и Sheets с результатами анализа"""
    try:
        service = GoogleDocsService()

        doc_content = f"""# 📝 Анализ встречи

## 📋 Резюме
{analysis.get('summary', 'Резюме не найдено')}

## 🔍 Ключевые моменты
{chr(10).join([f"- {point}" for point in analysis.get('key_points', [])])}

## ✅ Решения
{chr(10).join([f"- {decision}" for decision in analysis.get('decisions', [])])}

## 📄 Полный транскрипт
"""

        doc_url = service.create_doc(
            title=f"Voice2Action - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            content=doc_content
        )

        tasks = analysis.get('tasks', [])
        sheet_url = None
        if tasks:
            sheet_url = service.create_sheet(
                title=f"Задачи Voice2Action - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                tasks=tasks
            )
        else:
            sheet_url = "Нет задач для экспорта"

        logger.info(f"✅ Google Docs создан: {doc_url}")
        logger.info(f"✅ Google Sheet создан: {sheet_url}")

        return {
            "doc_url": doc_url,
            "sheet_url": sheet_url,
            "tasks_count": len(tasks)
        }

    except Exception as e:
        logger.error(f"Ошибка создания Google документов: {e}")
        return {"error": str(e)}


# --- ТЕСТ (для локальной разработки) ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        service = GoogleDocsService()

        doc_url = service.create_doc(
            "Тест Voice2Action",
            "Привет! Это тест документа, созданного через Service Account."
        )
        print(f"✅ Документ: {doc_url}")

        sheet_url = service.create_sheet(
            "Тест Задачи",
            [
                {
                    "description": "Сделать презентацию",
                    "deadline": "2025-11-05",
                    "assignee": "Антон",
                    "priority": "High"
                }
            ]
        )
        print(f"✅ Таблица: {sheet_url}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
