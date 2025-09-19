@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║        🤖 ENHANCED AUTONOMOUS MCP SERVER v2.0               ║
echo ║                                                              ║
echo ║  ✨ Запуск расширенной версии с AI агентом                  ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

echo [1/5] 🔍 Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ❌ Python не найден!
    echo 📦 Установите Python 3.8+ с https://python.org
    pause
    exit /b 1
)
echo [✅] Python найден

echo [2/5] 📦 Установка зависимостей...
pip install psutil requests beautifulsoup4 --quiet
echo [✅] Зависимости установлены

echo [3/5] 📁 Проверка файлов...
if not exist "enhanced_launcher.py" (
    echo [ERROR] ❌ enhanced_launcher.py не найден
    pause
    exit /b 1
)
echo [✅] Файлы найдены

echo [4/5] 📁 Создание структуры...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "config" mkdir config
if not exist "backups" mkdir backups
echo [✅] Структура создана

echo [5/5] 🚀 Запуск сервера...
echo.
echo 🎮 Запускается Enhanced MCP Server
echo ⚠️ Базовая версия - для полного функционала загрузите все модули
echo.

python enhanced_launcher.py

pause