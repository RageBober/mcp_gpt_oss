@echo off
echo ================================================================
echo        Autonomous GPT OSS 20B MCP Server - Windows Launcher
echo ================================================================
echo.

REM Проверка Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.8+
    echo Download from: https://python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found

REM Проверка Ollama
echo [2/5] Checking Ollama service...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama not found! Installing...
    echo Please install Ollama from: https://ollama.com/download
    pause
    exit /b 1
)
echo [OK] Ollama found

REM Проверка модели GPT OSS 20B
echo [3/5] Checking GPT OSS 20B model...
ollama list | findstr "gpt-oss:20b" >nul
if errorlevel 1 (
    echo [WARNING] GPT OSS 20B model not found. Downloading...
    echo This may take several minutes...
    ollama pull gpt-oss:20b
    if errorlevel 1 (
        echo [ERROR] Failed to download model
        pause
        exit /b 1
    )
)
echo [OK] GPT OSS 20B model ready

REM Запуск Ollama сервиса
echo [4/5] Starting Ollama service...
tasklist | findstr "ollama.exe" >nul
if errorlevel 1 (
    echo Starting Ollama in background...
    start /B ollama serve
    timeout /t 10 /nobreak >nul
    echo [OK] Ollama service started
) else (
    echo [OK] Ollama already running
)

REM Установка зависимостей Python
echo [5/5] Installing Python dependencies...
pip install --quiet psutil requests asyncio
if errorlevel 1 (
    echo [WARNING] Some packages may already be installed
)

REM Проверка MCP
python -c "import mcp" 2>nul
if errorlevel 1 (
    echo Installing MCP library...
    pip install mcp
)

echo.
echo ================================================================
echo                    STARTING MCP SERVER
echo ================================================================
echo.
echo 🎮 Control Center GUI will open automatically
echo 🎭 Emotional Display window will appear
echo 🚨 DO NOT enable unrestricted access unless testing!
echo.
echo Press Ctrl+C to stop the server
echo.

REM Запуск основного сервера
python main.py

pause
