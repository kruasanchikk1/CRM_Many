import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

print("=" * 50)
print(f"Ключ: {API_KEY[:10]}...{API_KEY[-10:]}")
print(f"Длина ключа: {len(API_KEY)} символов")
print(f"Folder ID: {FOLDER_ID}")
print("=" * 50)

# Тест подключения к SpeechKit
try:
    response = requests.post(
        "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
        headers={
            "Authorization": f"Api-Key {API_KEY}",
        },
        params={
            "folderId": FOLDER_ID,
            "lang": "ru-RU"
        },
        data=b"test",  # не аудио, просто для проверки
        timeout=10
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 400:
        print("✅ УСПЕХ! Ключ работает!")
        print("   (400 - ожидаемо, потому что отправлен не аудио-файл)")
        print(f"   Ответ: {response.text}")
    elif response.status_code == 401:
        print("❌ ОШИБКА: Неавторизованный доступ")
        print(f"   Ответ: {response.text}")
    else:
        print(f"⚠️  Неожиданный статус: {response.status_code}")
        print(f"   Ответ: {response.text}")

except Exception as e:
    print(f"❌ Ошибка подключения: {e}")