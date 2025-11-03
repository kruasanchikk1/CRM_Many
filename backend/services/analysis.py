import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
logger = logging.getLogger(__name__)


# Промпты для разных типов анализа
MEETING_PROMPT = """
Проанализируй транскрипт встречи и выполни следующее:

**Транскрипт:**
{transcript}

**Задачи:**
1. Создай краткое резюме (summary) встречи (3-5 предложений).
2. Извлеки все задачи в формате:
   Задача: [Краткое описание]
   Дедлайн: [Дата или "Не указан"]
   Ответственный: [Имя или "Не указан"]
   Приоритет: [Высокий/Средний/Низкий или "Не указан"]

**Формат ответа:**
## Summary
[Резюме встречи]

## Задачи
1. Задача: [Описание]
   Дедлайн: [Дата]
   Ответственный: [Имя]
   Приоритет: [Уровень]
"""

SALES_PROMPT = """
Проанализируй звонок продаж и предоставь детальный отчёт.

**Транскрипт:**
{transcript}

**Анализ должен включать:**

1. **Слова-паразиты**: 
   - Количество ("эээ", "мммм", "типа", "как бы")
   - Примеры с таймкодами

2. **Паузы**:
   - Количество пауз >3 секунд
   - Контекст (неуверенность, обдумывание)

3. **Уверенность речи**:
   - Оценка: Высокая / Средняя / Низкая
   - Обоснование

4. **Структура разговора**:
   - Процент времени говорения (менеджер vs клиент)
   - Количество открытых вопросов
   - Наличие активного слушания

5. **Возражения клиента**:
   - Список возражений
   - Как менеджер обработал каждое

6. **Рекомендации**:
   - 3-5 конкретных советов для улучшения
   - Приоритетная область для развития

**Формат ответа:**
## Summary
[Краткое резюме звонка]

## Анализ
[Детальный анализ по пунктам выше]

## Рекомендации
[Список рекомендаций]
"""

INTERVIEW_PROMPT = """
Проанализируй интервью и создай отчёт.

**Транскрипт:**
{transcript}

**Задачи:**
1. Краткое резюме интервью
2. Ключевые компетенции кандидата
3. Сильные стороны
4. Области для развития
5. Рекомендация (нанять/не нанять/следующий этап)

**Формат ответа:**
## Summary
[Резюме]

## Компетенции
[Список компетенций]

## Оценка
[Сильные стороны и области развития]

## Рекомендация
[Финальная рекомендация]
"""


async def analyze_transcript(transcript: str, analysis_type: str = "meeting", custom_prompt: str = None) -> str:
    """
    Анализ транскрипта через GPT-4o-mini
    
    Args:
        transcript: Текст транскрипта
        analysis_type: Тип анализа (meeting, sales, interview, custom)
        custom_prompt: Кастомный промпт (если analysis_type="custom")
    
    Returns:
        Текст анализа
    """
    try:
        # Выбор промпта
        if analysis_type == "sales":
            prompt = SALES_PROMPT.format(transcript=transcript)
        elif analysis_type == "interview":
            prompt = INTERVIEW_PROMPT.format(transcript=transcript)
        elif analysis_type == "custom" and custom_prompt:
            prompt = custom_prompt.format(transcript=transcript)
        else:
            prompt = MEETING_PROMPT.format(transcript=transcript)
        
        logger.info(f"Analyzing transcript with type: {analysis_type}")
        
        # Вызов GPT-4o-mini
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты ассистент для анализа деловых встреч и звонков."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        analysis = response.choices[0].message.content
        logger.info(f"Analysis completed, length: {len(analysis)} chars")
        
        return analysis
    
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise Exception(f"Не удалось проанализировать текст: {str(e)}")


async def generate_protocol(transcript: str, date: str = None, participants: str = None) -> str:
    """
    Генерация официального протокола встречи
    """
    prompt = f"""
Создай официальный протокол встречи на основе транскрипта.

**Структура протокола:**

# Протокол встречи
**Дата**: {date or "Не указана"}
**Участники**: {participants or "Не указаны"}

## 1. Повестка дня
[Список обсуждаемых тем]

## 2. Обсуждение
[Краткое описание каждой темы с ключевыми моментами]

## 3. Принятые решения
[Список всех решений с ответственными]

## 4. Действия
[Таблица: Задача | Ответственный | Срок]

## 5. Следующие шаги
[План на следующую встречу]

Транскрипт:
{transcript}

Протокол:
"""
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты секретарь, создающий официальные протоколы встреч."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        logger.error(f"Protocol generation failed: {e}")
        raise Exception(f"Не удалось создать протокол: {str(e)}")
