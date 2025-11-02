@echo off
echo Запуск Voice2Action бота на Python 3.12...
cd /d "D:\artemk111\LicenseFiles\Voice2Action\voice2action-site_v1\voice2action-site\telegram-bot"

:: Проверяем, установлен ли Python 3.12
py -3.12 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python 3.12 не найден!
    echo Установи с https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe
    pause
    exit /b 1
)

:: Устанавливаем зависимости
py -3.12 -m pip install --quiet python-telegram-bot==20.7 openai python-dotenv atlassian-python-api

:: Запускаем бота
py -3.12 bot.py
pause