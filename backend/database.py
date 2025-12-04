# database.py
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class TranscriptDB:
    def __init__(self, db_path: str = "voice2action.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Таблица для задач
        c.execute('''CREATE TABLE IF NOT EXISTS jobs
                    (id TEXT PRIMARY KEY,
                     filename TEXT,
                     transcript_text TEXT,
                     transcript_chars INTEGER,
                     status TEXT,
                     analysis_json TEXT,
                     created_at TIMESTAMP,
                     completed_at TIMESTAMP)''')

        # Таблица для анализа (нормализованная)
        c.execute('''CREATE TABLE IF NOT EXISTS analysis
                    (job_id TEXT PRIMARY KEY,
                     summary TEXT,
                     tasks_json TEXT,
                     key_points_json TEXT,
                     decisions_json TEXT,
                     raw_gpt_response TEXT,
                     FOREIGN KEY (job_id) REFERENCES jobs (id))''')

        # Таблица для задач из анализа
        c.execute('''CREATE TABLE IF NOT EXISTS extracted_tasks
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     job_id TEXT,
                     description TEXT,
                     deadline TEXT,
                     assignee TEXT,
                     priority TEXT,
                     FOREIGN KEY (job_id) REFERENCES jobs (id))''')

        conn.commit()
        conn.close()
        logger.info(f"База данных инициализирована: {self.db_path}")

    def create_job(self, job_id: str, filename: str) -> bool:
        """Создать новую задачу"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            c.execute('''INSERT INTO jobs 
                        (id, filename, status, created_at) 
                        VALUES (?, ?, ?, ?)''',
                      (job_id, filename, "processing", datetime.now()))

            conn.commit()
            conn.close()
            logger.info(f"Создана задача {job_id} для файла {filename}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания задачи: {e}")
            return False

    def update_transcript(self, job_id: str, transcript_text: str) -> bool:
        """Обновить транскрипт"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            c.execute('''UPDATE jobs 
                        SET transcript_text = ?, transcript_chars = ?, status = ?
                        WHERE id = ?''',
                      (transcript_text, len(transcript_text), "transcribed", job_id))

            conn.commit()
            conn.close()
            logger.info(f"Обновлён транскрипт задачи {job_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления транскрипта: {e}")
            return False

    def save_analysis(self, job_id: str, analysis_data: Dict[str, Any], raw_gpt_response: str = "") -> bool:
        """Сохранить результаты анализа"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            # Обновляем основную таблицу
            c.execute('''UPDATE jobs 
                        SET analysis_json = ?, status = ?, completed_at = ?
                        WHERE id = ?''',
                      (json.dumps(analysis_data, ensure_ascii=False),
                       "completed",
                       datetime.now(),
                       job_id))

            # Сохраняем в таблицу analysis
            c.execute('''INSERT OR REPLACE INTO analysis
                        (job_id, summary, tasks_json, key_points_json, decisions_json, raw_gpt_response)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                      (job_id,
                       analysis_data.get("summary", ""),
                       json.dumps(analysis_data.get("tasks", []), ensure_ascii=False),
                       json.dumps(analysis_data.get("key_points", []), ensure_ascii=False),
                       json.dumps(analysis_data.get("decisions", []), ensure_ascii=False),
                       raw_gpt_response))

            # Сохраняем задачи отдельно (если есть)
            tasks = analysis_data.get("tasks", [])
            for task in tasks:
                c.execute('''INSERT INTO extracted_tasks
                            (job_id, description, deadline, assignee, priority)
                            VALUES (?, ?, ?, ?, ?)''',
                          (job_id,
                           task.get("description", ""),
                           task.get("deadline", "Не указан"),
                           task.get("assignee", "Не указан"),
                           task.get("priority", "Medium")))

            conn.commit()
            conn.close()
            logger.info(f"Сохранён анализ задачи {job_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения анализа: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Получить задачу по ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Получаем основную информацию
            c.execute('''SELECT * FROM jobs WHERE id = ?''', (job_id,))
            job_row = c.fetchone()

            if not job_row:
                return None

            job = dict(job_row)

            # Получаем анализ если есть
            c.execute('''SELECT * FROM analysis WHERE job_id = ?''', (job_id,))
            analysis_row = c.fetchone()

            if analysis_row:
                analysis = dict(analysis_row)
                # Парсим JSON поля
                job["analysis"] = {
                    "summary": analysis["summary"],
                    "tasks": json.loads(analysis["tasks_json"]) if analysis["tasks_json"] else [],
                    "key_points": json.loads(analysis["key_points_json"]) if analysis["key_points_json"] else [],
                    "decisions": json.loads(analysis["decisions_json"]) if analysis["decisions_json"] else []
                }
            else:
                job["analysis"] = None

            # Получаем извлечённые задачи
            c.execute('''SELECT * FROM extracted_tasks WHERE job_id = ?''', (job_id,))
            extracted_tasks = [dict(row) for row in c.fetchall()]
            job["extracted_tasks"] = extracted_tasks

            conn.close()
            return job
        except Exception as e:
            logger.error(f"Ошибка получения задачи: {e}")
            return None

    def get_all_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить все задачи"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute('''SELECT id, filename, status, created_at, completed_at 
                        FROM jobs 
                        ORDER BY created_at DESC 
                        LIMIT ?''', (limit,))

            jobs = []
            for row in c.fetchall():
                job = dict(row)
                # Получаем базовую информацию об анализе
                c2 = conn.cursor()
                c2.execute('''SELECT summary FROM analysis WHERE job_id = ?''', (job["id"],))
                analysis_row = c2.fetchone()
                job["has_analysis"] = analysis_row is not None

                jobs.append(job)

            conn.close()
            return jobs
        except Exception as e:
            logger.error(f"Ошибка получения всех задач: {e}")
            return []

    def delete_job(self, job_id: str) -> bool:
        """Удалить задачу"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            # Удаляем в правильном порядке из-за foreign keys
            c.execute('''DELETE FROM extracted_tasks WHERE job_id = ?''', (job_id,))
            c.execute('''DELETE FROM analysis WHERE job_id = ?''', (job_id,))
            c.execute('''DELETE FROM jobs WHERE id = ?''', (job_id,))

            conn.commit()
            conn.close()
            logger.info(f"Удалена задача {job_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления задачи: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            stats = {}

            # Общее количество
            c.execute('''SELECT COUNT(*) FROM jobs''')
            stats["total_jobs"] = c.fetchone()[0]

            # По статусам
            c.execute('''SELECT status, COUNT(*) FROM jobs GROUP BY status''')
            stats["by_status"] = dict(c.fetchall())

            # Последние 7 дней
            c.execute('''SELECT DATE(created_at), COUNT(*) 
                        FROM jobs 
                        WHERE created_at > datetime('now', '-7 days')
                        GROUP BY DATE(created_at)''')
            stats["last_7_days"] = dict(c.fetchall())

            # Средняя длина транскрипта
            c.execute('''SELECT AVG(transcript_chars) FROM jobs WHERE transcript_chars IS NOT NULL''')
            stats["avg_transcript_length"] = round(c.fetchone()[0] or 0, 2)

            conn.close()
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}


# Глобальный экземпляр БД
db = TranscriptDB()