import os
import logging
from datetime import datetime
from atlassian import Jira
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Jira клиент
JIRA_URL = os.getenv('JIRA_URL')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', 'V2A')

try:
    jira = Jira(
        url=JIRA_URL,
        username=JIRA_EMAIL,
        password=JIRA_API_TOKEN,
        cloud=True
    )
    logger.info("Jira client initialized")
except Exception as e:
    logger.warning(f"Jira initialization failed: {e}")
    jira = None


def create_jira_issues(tasks: list) -> list:
    """
    Создание тикетов в Jira из списка задач
    
    Args:
        tasks: Список задач с полями description, deadline, assignee, priority
    
    Returns:
        Список созданных тикетов с key и url
    """
    if not jira:
        logger.error("Jira client not initialized")
        raise Exception("Jira не настроен. Проверь переменные окружения.")
    
    created_issues = []
    
    for task in tasks:
        try:
            # Формирование описания
            description = f"""
Источник: Voice2Action Bot
Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Описание задачи:
{task.get('description', 'Нет описания')}

Ответственный: {task.get('assignee', 'Не указан')}
Приоритет: {task.get('priority', 'Средний')}
"""
            
            # Маппинг приоритета
            priority_map = {
                'Высокий': 'High',
                'Средний': 'Medium',
                'Низкий': 'Low'
            }
            priority = priority_map.get(task.get('priority', 'Средний'), 'Medium')
            
            # Создание тикета
            fields = {
                'project': {'key': JIRA_PROJECT_KEY},
                'summary': task.get('description', 'Задача из Voice2Action')[:255],
                'description': description,
                'issuetype': {'name': 'Task'},
                'priority': {'name': priority}
            }
            
            # Добавляем дедлайн, если указан
            deadline = task.get('deadline', 'Не указан')
            if deadline != 'Не указан':
                try:
                    # Преобразуем дату в формат YYYY-MM-DD
                    if len(deadline.split('-')) == 3:
                        fields['duedate'] = deadline
                except:
                    logger.warning(f"Invalid deadline format: {deadline}")
            
            # Создаём тикет
            issue = jira.issue_create(fields=fields)
            
            issue_key = issue['key']
            issue_url = f"{JIRA_URL}/browse/{issue_key}"
            
            created_issues.append({
                'key': issue_key,
                'url': issue_url,
                'summary': fields['summary']
            })
            
            logger.info(f"Created Jira issue: {issue_key}")
        
        except Exception as e:
            logger.error(f"Failed to create Jira issue: {e}")
            # Продолжаем создавать другие тикеты
            continue
    
    if not created_issues:
        raise Exception("Не удалось создать ни одного тикета в Jira")
    
    return created_issues


def get_jira_project_info():
    """Получить информацию о проекте (для тестирования)"""
    if not jira:
        return None
    
    try:
        project = jira.project(JIRA_PROJECT_KEY)
        return {
            'key': project['key'],
            'name': project['name'],
            'lead': project['lead']['displayName']
        }
    except Exception as e:
        logger.error(f"Failed to get project info: {e}")
        return None


def test_jira_connection():
    """Тестирование подключения к Jira"""
    if not jira:
        return False
    
    try:
        jira.projects()
        logger.info("Jira connection successful")
        return True
    except Exception as e:
        logger.error(f"Jira connection failed: {e}")
        return False
