#!/bin/bash

echo "================================================================"
echo "        Autonomous GPT OSS 20B MCP Server - Linux Launcher"
echo "================================================================"
echo

# Проверка Python
echo "[1/5] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found! Installing..."
    sudo apt update && sudo apt install python3 python3-pip python3-venv python3-tk -y
fi
echo "[OK] Python found"

# Проверка Ollama
echo "[2/5] Checking Ollama service..."
if ! command -v ollama &> /dev/null; then
    echo "[ERROR] Ollama not found! Installing..."
    curl -fsSL https://ollama.com/install.sh | sh
fi
echo "[OK] Ollama found"

# Проверка модели GPT OSS 20B
echo "[3/5] Checking GPT OSS 20B model..."
if ! ollama list | grep -q "gpt-oss:20b"; then
    echo "[WARNING] GPT OSS 20B model not found. Downloading..."
    echo "This may take several minutes..."
    ollama pull gpt-oss:20b
fi
echo "[OK] GPT OSS 20B model ready"

# Запуск Ollama сервиса
echo "[4/5] Starting Ollama service..."
if ! pgrep -f "ollama serve" > /dev/null; then
    echo "Starting Ollama in background..."
    ollama serve &
    sleep 10
    echo "[OK] Ollama service started"
else
    echo "[OK] Ollama already running"
fi

# Установка зависимостей Python
echo "[5/5] Installing Python dependencies..."
pip3 install --quiet psutil requests asyncio

# Проверка MCP
if ! python3 -c "import mcp" 2>/dev/null; then
    echo "Installing MCP library..."
    pip3 install mcp
fi

echo
echo "================================================================"
echo "                    STARTING MCP SERVER"
echo "================================================================"
echo
echo "🎮 Control Center GUI will open automatically"
echo "🎭 Emotional Display window will appear"
echo "🚨 DO NOT enable unrestricted access unless testing!"
echo
echo "Press Ctrl+C to stop the server"
echo

# Запуск основного сервера
python3 main.py
