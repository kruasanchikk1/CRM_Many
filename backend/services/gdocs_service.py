import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Scopes для Google API
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
        self._authenticate()
    
    def _authenticate(self):
        """Авторизация через Service Account"""
        
        # Проверяем переменную окружения GOOGLE_SERVICE_ACCOUNT_JSON
        service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        
        if not service_account_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON не найдена в переменных окружения")
        
        try:
            # Парсим JSON из переменной окружения
            service_account_info = json.loads(service_account_json)
            
            # Создаём credentials
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=SCOPES
            )
            
            # Создаём сервисы
            self.docs_service = build('docs', 'v1', credentials=credentials)
            self.sheets_service = build('sheets', 'v4', credentials=credentials)
            self.drive_service = build('drive', 'v3', credentials=credentials)
            
            logger.info("✅ Google API подключён через Service Account")
        
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON содержит невалидный JSON")
        
        except Exception as e:
            logger.error(f"Ошибка авторизации Google API: {e}")
            raise
    
    def create_doc(self, title: str, content: str) -> str:
        """Создаёт Google Doc"""
        try:
            # Создание документа
            doc = self.docs_service.documents().create(
                body={'title': title}
            ).execute()
            
            doc_id = doc['documentId']
            
            # Добавление контента
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
            
            # Делаем документ доступным для всех с правом на чтение
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
            # Создание таблицы
            spreadsheet = {
                'properties': {'title': title},
                'sheets': [{'properties': {'title': 'Задачи'}}]
            }
            
            sheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet
            ).execute()
            
            sheet_id = sheet['spreadsheetId']
            
            # Заголовки и данные
            values = [['Задача', 'Дедлайн', 'Ответственный', 'Приоритет']]
            
            for task in tasks:
                values.append([
                    task.get('description', ''),
                    task.get('deadline', 'Не указан'),
                    task.get('assignee', 'Не указан'),
                    task.get('priority', 'Medium')
                ])
            
            # Запись данных
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='Задачи!A1',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            
            # Делаем таблицу доступной для всех
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