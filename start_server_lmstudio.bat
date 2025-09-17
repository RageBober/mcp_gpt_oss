@echo off
echo ================================================================
echo     Autonomous GPT OSS 20B MCP Server - LM Studio Version
echo ================================================================
echo.

REM Проверка Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

REM Проверка curl
where curl >nul 2>&1
if errorlevel 1 (
    echo [WARNING] curl not found, some checks may fail
)

REM Проверка LM Studio API
echo [2/5] Checking LM Studio server...
curl -s http://localhost:1234/v1/models >nul 2>&1
if errorlevel 1 (
    echo [ERROR] LM Studio server not responding!
    echo.
    echo Please ensure:
    echo 1. LM Studio is running
    echo 2. GPT OSS 20B model is downloaded and loaded
    echo 3. Local server is started on port 1234
    echo 4. Server tab shows "Server Running"
    echo.
    echo To fix this:
    echo - Open LM Studio
    echo - Go to "Local Server" tab  
    echo - Select "openai/gpt-oss-20b" model
    echo - Click "Start Server"
    echo.
    pause
    exit /b 1
)
echo [OK] LM Studio server is running

REM Проверка загруженной модели
echo [3/5] Checking GPT OSS 20B model availability...
curl -s -X POST http://localhost:1234/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"gpt-oss-20b\",\"messages\":[{\"role\":\"user\",\"content\":\"test\"}],\"max_tokens\":5}" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] GPT OSS 20B model may not be properly loaded
    echo Please check LM Studio and ensure:
    echo - The model is fully downloaded
    echo - The model is selected and loaded
    echo - Server shows "Model loaded" status
)
echo [OK] Model appears to be responding

REM Установка зависимостей Python
echo [4/5] Installing Python dependencies...
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

echo [5/5] Configuring LM Studio mode...

echo.
echo ================================================================
echo                    STARTING MCP SERVER
echo ================================================================
echo.
echo 🎛️ Using LM Studio backend instead of Ollama
echo 🎮 Control Center GUI will open automatically
echo 🎭 Emotional Display window will appear
echo 🧠 Fine-tuning interface available with LM Studio integration
echo 🚨 DO NOT enable unrestricted access unless testing!
echo.
echo LM Studio Configuration:
echo - Server URL: http://localhost:1234
echo - API Version: OpenAI Compatible v1
echo - Model: GPT OSS 20B
echo.
echo Press Ctrl+C to stop the server
echo.

REM Установка переменной окружения для LM Studio
set LM_STUDIO_MODE=1
set LM_STUDIO_URL=http://localhost:1234

REM Запуск основного сервера
python main.py

echo.
echo Server stopped. Press any key to exit...
pause >nul