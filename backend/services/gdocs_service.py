import os
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'  # ← ДОБАВЛЕНО


class GoogleDocsService:
    def __init__(self):
        self.docs_service = None
        self.sheets_service = None
        self.drive_service = None
        self._authenticate()

    def _authenticate(self):
        """OAuth через Service Account (для Render) или token.json (локально)"""
        import json

        creds = None

        # Проверка на Service Account (для продакшена на Render)
        if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
            try:
                service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
                from google.oauth2 import service_account

                creds = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=SCOPES
                )
                logger.info("✅ Service Account подключён (Render)")
            except Exception as e:
                logger.error(f"❌ Ошибка Service Account: {e}")
                raise

        # Локальная разработка (через token.json)
        else:
            if os.path.exists(TOKEN_FILE):
                try:
                    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
                    logger.info("✅ Токен загружен из token.json (локально)")
                except Exception as e:
                    logger.warning(f"⚠️ Токен повреждён, удаляем: {e}")
                    os.remove(TOKEN_FILE)
                    creds = None

            if creds and creds.expired:
                if creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        logger.info("✅ Токен обновлён через refresh_token")

                        with open(TOKEN_FILE, 'w') as token:
                            token.write(creds.to_json())
                        logger.info("✅ Обновлённый токен сохранён")
                    except Exception as e:
                        logger.error(f"❌ Не удалось обновить токен: {e}")
                        os.remove(TOKEN_FILE)
                        creds = None
                else:
                    logger.warning("⚠️ refresh_token отсутствует, удаляем token.json")
                    os.remove(TOKEN_FILE)
                    creds = None

            if not creds or not creds.valid:
                if not os.path.exists(CREDENTIALS_FILE):
                    raise FileNotFoundError(f"❌ {CREDENTIALS_FILE} не найден!")

                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE,
                    SCOPES,
                    redirect_uri='http://localhost:8000/'
                )

                creds = flow.run_local_server(
                    port=8000,
                    access_type='offline',
                    prompt='consent'
                )

                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                logger.info("✅ Новый токен сохранён в token.json")

        # Подключить API
        try:
            self.docs_service = build('docs', 'v1', credentials=creds)
            self.sheets_service = build('sheets', 'v4', credentials=creds)
            self.drive_service = build('drive', 'v3', credentials=creds)
            logger.info("✅ Google API подключён")
        except Exception as e:
            logger.error(f"❌ Не удалось подключить Google API: {e}")
            raise

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
        """Создаёт Google Sheet"""
        try:
            spreadsheet = {
                'properties': {'title': title},
                'sheets': [{'properties': {'title': 'Задачи'}}]
            }
            sheet = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
            sheet_id = sheet['spreadsheetId']

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        service = GoogleDocsService()
        doc_url = service.create_doc(
            "Тест Voice2Action",
            "Это автоматически созданный документ через AI."
        )
        print(f"Документ: {doc_url}")

        sheet_url = service.create_sheet("Тест Задачи", [
            {"description": "Сделать презентацию", "deadline": "2025-11-05", "assignee": "Антон"}
        ])
        print(f"Таблица: {sheet_url}")
    except Exception as e:
        print(f"Ошибка: {e}")