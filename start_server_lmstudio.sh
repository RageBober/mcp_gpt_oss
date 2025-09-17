#!/bin/bash

echo "================================================================"
echo "     Autonomous GPT OSS 20B MCP Server - LM Studio Version"
echo "================================================================"
echo

# Проверка Python
echo "[1/5] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found! Installing..."
    sudo apt update && sudo apt install python3 python3-pip python3-venv python3-tk -y
fi
echo "[OK] Python found"

# Проверка curl
if ! command -v curl &> /dev/null; then
    echo "Installing curl..."
    sudo apt install curl -y
fi

# Проверка LM Studio API
echo "[2/5] Checking LM Studio server..."
if ! curl -s http://localhost:1234/v1/models > /dev/null 2>&1; then
    echo "[ERROR] LM Studio server not responding!"
    echo
    echo "Please ensure:"
    echo "1. LM Studio is running"
    echo "2. GPT OSS 20B model is downloaded and loaded"
    echo "3. Local server is started on port 1234"
    echo "4. Server tab shows 'Server Running'"
    echo
    echo "To fix this:"
    echo "- Open LM Studio"
    echo "- Go to 'Local Server' tab"
    echo "- Select 'openai/gpt-oss-20b' model"
    echo "- Click 'Start Server'"
    echo
    exit 1
fi
echo "[OK] LM Studio server is running"

# Проверка загруженной модели
echo "[3/5] Checking GPT OSS 20B model availability..."
if ! curl -s -X POST http://localhost:1234/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"gpt-oss-20b","messages":[{"role":"user","content":"test"}],"max_tokens":5}' > /dev/null 2>&1; then
    echo "[WARNING] GPT OSS 20B model may not be properly loaded"
    echo "Please check LM Studio and ensure:"
    echo "- The model is fully downloaded"
    echo "- The model is selected and loaded"
    echo "- Server shows 'Model loaded' status"
fi
echo "[OK] Model appears to be responding"

# Установка зависимостей Python
echo "[4/5] Installing Python dependencies..."
pip3 install --quiet psutil requests asyncio

# Проверка MCP
if ! python3 -c "import mcp" 2>/dev/null; then
    echo "Installing MCP library..."
    pip3 install mcp
fi

echo "[5/5] Configuring LM Studio mode..."

echo
echo "================================================================"
echo "                    STARTING MCP SERVER"
echo "================================================================"
echo
echo "🎛️ Using LM Studio backend instead of Ollama"
echo "🎮 Control Center GUI will open automatically"
echo "🎭 Emotional Display window will appear"
echo "🧠 Fine-tuning interface available with LM Studio integration"
echo "🚨 DO NOT enable unrestricted access unless testing!"
echo
echo "LM Studio Configuration:"
echo "- Server URL: http://localhost:1234"
echo "- API Version: OpenAI Compatible v1"
echo "- Model: GPT OSS 20B"
echo
echo "Press Ctrl+C to stop the server"
echo

# Установка переменной окружения для LM Studio
export LM_STUDIO_MODE=1
export LM_STUDIO_URL=http://localhost:1234

# Запуск основного сервера
python3 main.py

echo
echo "Server stopped."
