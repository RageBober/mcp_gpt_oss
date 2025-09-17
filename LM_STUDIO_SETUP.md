# 🎛️ Интеграция с LM Studio

Этот файл содержит инструкции по настройке MCP сервера для работы с LM Studio вместо Ollama.

## 📋 Настройка LM Studio

### 1. Установка и настройка LM Studio

1. **Скачайте LM Studio** с официального сайта: https://lmstudio.ai/
2. **Установите и запустите** LM Studio
3. **Скачайте GPT OSS 20B модель:**
   - Откройте вкладку "Search"
   - Найдите "openai/gpt-oss-20b"
   - Скачайте модель (это займет время)

### 2. Запуск локального сервера

В LM Studio:
1. **Перейдите во вкладку "Local Server"**
2. **Выберите модель** "openai/gpt-oss-20b"
3. **Нажмите "Start Server"**
4. **Убедитесь**, что сервер запущен на `http://localhost:1234`

### 3. Обновите конфигурацию MCP сервера

Откройте файл `config/server_config.json` и измените настройки:

```json
{
  "server": {
    "name": "autonomous-gpt-oss-20b-lmstudio",
    "version": "1.0.0",
    "host": "localhost",
    "port": 8080,
    "max_connections": 10
  },
  "gpt_oss": {
    "model_name": "openai/gpt-oss-20b",
    "base_url": "http://localhost:1234",
    "api_endpoint": "/v1/chat/completions",
    "max_tokens": 4000,
    "temperature": 0.7,
    "reasoning_level": "medium"
  },
  "lm_studio": {
    "enabled": true,
    "local_server_url": "http://localhost:1234",
    "model_loaded_check": true,
    "timeout": 60
  },
  "monitoring": {
    "update_interval": 5,
    "log_level": "INFO",
    "max_log_files": 10,
    "emotion_update_rate": 10
  },
  "database": {
    "path": "data/autonomous_tasks.db",
    "backup_interval": 3600,
    "max_task_history": 1000
  }
}
```

### 4. Создайте специальный скрипт запуска для LM Studio

Windows (`start_server_lmstudio.bat`):
```batch
@echo off
echo ================================================================
echo     Autonomous GPT OSS 20B MCP Server - LM Studio Version
echo ================================================================
echo.

REM Проверка Python
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.8+
    pause
    exit /b 1
)
echo [OK] Python found

REM Проверка LM Studio API
echo [2/4] Checking LM Studio server...
curl -s http://localhost:1234/v1/models >nul 2>&1
if errorlevel 1 (
    echo [ERROR] LM Studio server not responding!
    echo Please ensure:
    echo 1. LM Studio is running
    echo 2. GPT OSS 20B model is loaded
    echo 3. Local server is started on port 1234
    pause
    exit /b 1
)
echo [OK] LM Studio server is running

REM Установка зависимостей Python
echo [3/4] Installing Python dependencies...
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

echo [4/4] Checking GPT OSS 20B model availability...
curl -s -X POST http://localhost:1234/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"gpt-oss-20b\",\"messages\":[{\"role\":\"user\",\"content\":\"test\"}],\"max_tokens\":5}" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] GPT OSS 20B model may not be properly loaded
    echo Please check LM Studio and ensure the model is loaded
)

echo.
echo ================================================================
echo                    STARTING MCP SERVER
echo ================================================================
echo.
echo 🎛️ Using LM Studio instead of Ollama
echo 🎮 Control Center GUI will open automatically
echo 🎭 Emotional Display window will appear
echo 🚨 DO NOT enable unrestricted access unless testing!
echo.
echo Press Ctrl+C to stop the server
echo.

REM Установка переменной окружения для LM Studio
set LM_STUDIO_MODE=1

REM Запуск основного сервера
python main.py

pause
```

Linux (`start_server_lmstudio.sh`):
```bash
#!/bin/bash

echo "================================================================"
echo "     Autonomous GPT OSS 20B MCP Server - LM Studio Version"
echo "================================================================"
echo

# Проверка Python
echo "[1/4] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found!"
    exit 1
fi
echo "[OK] Python found"

# Проверка LM Studio API
echo "[2/4] Checking LM Studio server..."
if ! curl -s http://localhost:1234/v1/models > /dev/null 2>&1; then
    echo "[ERROR] LM Studio server not responding!"
    echo "Please ensure:"
    echo "1. LM Studio is running"
    echo "2. GPT OSS 20B model is loaded"
    echo "3. Local server is started on port 1234"
    exit 1
fi
echo "[OK] LM Studio server is running"

# Установка зависимостей Python
echo "[3/4] Installing Python dependencies..."
pip3 install --quiet psutil requests asyncio

# Проверка MCP
if ! python3 -c "import mcp" 2>/dev/null; then
    echo "Installing MCP library..."
    pip3 install mcp
fi

echo "[4/4] Checking GPT OSS 20B model availability..."
if ! curl -s -X POST http://localhost:1234/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"gpt-oss-20b","messages":[{"role":"user","content":"test"}],"max_tokens":5}' > /dev/null 2>&1; then
    echo "[WARNING] GPT OSS 20B model may not be properly loaded"
    echo "Please check LM Studio and ensure the model is loaded"
fi

echo
echo "================================================================"
echo "                    STARTING MCP SERVER"
echo "================================================================"
echo
echo "🎛️ Using LM Studio instead of Ollama"
echo "🎮 Control Center GUI will open automatically"
echo "🎭 Emotional Display window will appear"  
echo "🚨 DO NOT enable unrestricted access unless testing!"
echo
echo "Press Ctrl+C to stop the server"
echo

# Установка переменной окружения для LM Studio
export LM_STUDIO_MODE=1

# Запуск основного сервера
python3 main.py
```

### 5. Обновите основной код для поддержки LM Studio

Создайте файл `lm_studio_adapter.py`:

```python
import os
import requests
import json
from typing import Dict, Any, List

class LMStudioAdapter:
    """Адаптер для работы с LM Studio API"""
    
    def __init__(self, base_url="http://localhost:1234"):
        self.base_url = base_url
        self.api_endpoint = "/v1/chat/completions"
        self.models_endpoint = "/v1/models"
        
    def check_server_status(self) -> bool:
        """Проверка статуса LM Studio сервера"""
        try:
            response = requests.get(f"{self.base_url}{self.models_endpoint}", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_available_models(self) -> List[str]:
        """Получение списка доступных моделей"""
        try:
            response = requests.get(f"{self.base_url}{self.models_endpoint}", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                return [model["id"] for model in models_data.get("data", [])]
            return []
        except:
            return []
    
    def send_chat_request(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """Отправка запроса к LM Studio"""
        payload = {
            "model": kwargs.get("model", "gpt-oss-20b"),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 4000),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": kwargs.get("stream", False)
        }
        
        try:
            response = requests.post(
                f"{self.base_url}{self.api_endpoint}",
                json=payload,
                timeout=kwargs.get("timeout", 60)
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"LM Studio API error: {response.status_code}",
                    "details": response.text
                }
        except Exception as e:
            return {
                "error": f"Connection error: {str(e)}"
            }
    
    def test_model_response(self, model_name="gpt-oss-20b") -> Dict[str, Any]:
        """Тестирование ответа модели"""
        test_messages = [
            {"role": "user", "content": "Hello! Can you confirm you're GPT OSS 20B?"}
        ]
        
        return self.send_chat_request(test_messages, model=model_name, max_tokens=100)


# Функция для автоматического обнаружения режима
def get_llm_backend():
    """Автоматическое определение доступного бэкенда"""
    lm_studio = LMStudioAdapter()
    
    if os.getenv("LM_STUDIO_MODE") == "1" or lm_studio.check_server_status():
        return "lm_studio", lm_studio
    else:
        return "ollama", None
```

### 6. Обновите модуль дообучения для LM Studio

В файле `finetuning.py` найдите функцию `generate_example_variations()` и замените вызов Ollama API:

```python
def generate_example_variations(self):
    """Генерация вариаций текущего примера через GPT OSS 20B (LM Studio)"""
    input_text = self.input_text.get('1.0', tk.END).strip()
    
    if not input_text:
        messagebox.showwarning("Warning", "Please provide input text to generate variations")
        return
    
    self.update_status("Generating variations...")
    
    def generate_variations():
        try:
            from lm_studio_adapter import LMStudioAdapter
            
            lm_studio = LMStudioAdapter()
            
            if not lm_studio.check_server_status():
                self.window.after(0, lambda: self.update_status("LM Studio server not available"))
                return
            
            variations_prompt = f"""Generate 3 similar but different training examples based on this input:

Input: {input_text}

Create variations that:
1. Use different wording but same intent
2. Include edge cases or different parameters
3. Show different levels of detail in responses

Format as JSON array with objects containing 'input' and 'output' fields."""
            
            messages = [{"role": "user", "content": variations_prompt}]
            response = lm_studio.send_chat_request(messages, temperature=0.8)
            
            if "error" not in response:
                variations_text = response["choices"][0]["message"]["content"]
                
                # Попытка парсинга JSON
                try:
                    json_match = re.search(r'\[.*\]', variations_text, re.DOTALL)
                    if json_match:
                        variations_data = json.loads(json_match.group())
                        
                        cursor = self.training_db.cursor()
                        added_count = 0
                        
                        for variation in variations_data:
                            if isinstance(variation, dict) and 'input' in variation and 'output' in variation:
                                cursor.execute(
                                    "INSERT INTO training_examples (category, input_text, expected_output) VALUES (?, ?, ?)",
                                    (self.category_var.get(), variation['input'], variation['output'])
                                )
                                added_count += 1
                        
                        self.training_db.commit()
                        self.window.after(0, lambda: self.update_status(f"Generated {added_count} variations"))
                        self.window.after(0, self.update_preview)
                        self.window.after(0, self.refresh_library)
                        
                    else:
                        self.window.after(0, lambda: self.update_status("Failed to parse variations"))
                        
                except json.JSONDecodeError:
                    self.window.after(0, lambda: self.update_status("Failed to parse variations as JSON"))
                    
            else:
                self.window.after(0, lambda: self.update_status(f"LM Studio error: {response['error']}"))
                
        except Exception as e:
            self.window.after(0, lambda: self.update_status(f"Error: {str(e)}"))
    
    threading.Thread(target=generate_variations, daemon=True).start()
```

## 🎯 Преимущества LM Studio

**По сравнению с Ollama:**
- ✅ **GUI интерфейс** - удобнее управлять моделями
- ✅ **Лучшая производительность** на некоторых системах  
- ✅ **Поддержка GPU** с оптимизацией
- ✅ **Мониторинг ресурсов** встроенный
- ✅ **Простая смена моделей** через интерфейс

## 🚀 Запуск с LM Studio

1. **Убедитесь, что LM Studio запущен** с загруженной моделью GPT OSS 20B
2. **Запустите новый скрипт:**
   ```bash
   # Windows
   start_server_lmstudio.bat
   
   # Linux  
   ./start_server_lmstudio.sh
   ```
3. **Проверьте подключение** - в логах должно появиться "Using LM Studio backend"

## 🔧 Настройка производительности

В LM Studio настройте:
- **GPU Layers**: максимальное значение для вашей GPU
- **Context Length**: 4096 или 8192 для лучшей работы
- **Batch Size**: оптимизируйте под вашу систему

---

**Теперь ваш MCP сервер будет работать с LM Studio вместо Ollama! 🎛️**