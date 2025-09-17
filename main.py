import asyncio
import json
import subprocess
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
import psutil
import ctypes
from typing import Dict, List, Any, Optional
import logging
import sqlite3
import requests
import random
import colorsys
import math

# Импорт MCP компонентов
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import (
        CallToolRequest,
        ListToolsRequest,
        Tool,
        TextContent,
        GetPromptRequest,
        Prompt,
        PromptArgument
    )
except ImportError:
    print("⚠️ MCP library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp"])
    print("✅ MCP library installed. Please restart the application.")
    sys.exit(1)

# Импорт адаптера LM Studio
try:
    from lm_studio_adapter import LMStudioAdapter, get_llm_backend, send_llm_request, llm_manager
    LM_STUDIO_AVAILABLE = True
except ImportError:
    print("⚠️ LM Studio adapter not found. Only Ollama support available.")
    LM_STUDIO_AVAILABLE = False
    llm_manager = None

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/main.log'),
        logging.StreamHandler()
    ]
)

class AutonomousGPTServer:
    """Основной сервер для автономного GPT OSS 20B"""
    
    def __init__(self):
        self.running = False
        self.gui_thread = None
        self.monitoring_thread = None
        self.emotional_display = None
        self.control_center = None
        self.fine_tuning_interface = None
        
        # Определение backend'а
        self.backend_type = "unknown"
        self.llm_adapter = None
        self.init_llm_backend()
        
        # Системные параметры
        self.system_stats = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "gpu_usage": 0.0,
            "model_status": "unknown",
            "requests_count": 0,
            "errors_count": 0
        }
        
        # Настройки безопасности
        self.security_settings = {
            "unrestricted_access": False,
            "file_operations": "read_only",
            "network_access": "localhost",
            "auto_optimize": False,
            "backup_before_changes": True
        }
        
        # Инициализация
        self.create_directories()
        self.init_database()
        
    def init_llm_backend(self):
        """Инициализация LLM backend'а"""
        if LM_STUDIO_AVAILABLE:
            try:
                backend_type, adapter = get_llm_backend()
                self.backend_type = backend_type
                self.llm_adapter = adapter
                logging.info(f"✅ Using {backend_type} backend")
                
                if backend_type == "lm_studio" and adapter:
                    # Тест подключения к LM Studio
                    status = adapter.check_server_status()
                    if status:
                        logging.info("✅ LM Studio connection successful")
                    else:
                        logging.warning("⚠️ LM Studio server not responding, will retry later")
                        
                elif backend_type == "ollama":
                    logging.info("✅ Using Ollama as fallback backend")
                    
            except Exception as e:
                logging.error(f"❌ Failed to initialize LLM backend: {e}")
                self.backend_type = "error"
        else:
            # Проверка Ollama без LM Studio адаптера
            try:
                response = requests.get("http://localhost:11434/api/tags", timeout=3)
                if response.status_code == 200:
                    self.backend_type = "ollama"
                    logging.info("✅ Using Ollama backend")
                else:
                    self.backend_type = "error"
                    logging.error("❌ No LLM backend available")
            except:
                self.backend_type = "error"
                logging.error("❌ No LLM backend available")
    
    def create_directories(self):
        """Создание необходимых директорий"""
        directories = ['data', 'logs', 'checkpoints', 'config', 'gui', 'tools']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def init_database(self):
        """Инициализация базы данных"""
        db_path = 'data/autonomous_gpt.db'
        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    description TEXT,
                    data TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS model_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    backend_type TEXT,
                    prompt TEXT,
                    response TEXT,
                    response_time FLOAT,
                    tokens_used INTEGER,
                    status TEXT
                )
            ''')
            
    def log_event(self, event_type: str, description: str, data: Dict = None):
        """Логирование системных событий"""
        try:
            with sqlite3.connect('data/autonomous_gpt.db') as conn:
                conn.execute(
                    "INSERT INTO system_events (event_type, description, data) VALUES (?, ?, ?)",
                    (event_type, description, json.dumps(data) if data else None)
                )
        except Exception as e:
            logging.error(f"Failed to log event: {e}")
    
    def start_monitoring(self):
        """Запуск мониторинга системы"""
        def monitor():
            if self.running:
                try:
                    # Системная статистика
                    self.system_stats["cpu_usage"] = psutil.cpu_percent()
                    self.system_stats["memory_usage"] = psutil.virtual_memory().percent

                    # GPU статистика (если доступна)
                    try:
                        import gpustat
                        gpu_stats = gpustat.new_query()
                        if gpu_stats:
                            self.system_stats["gpu_usage"] = gpu_stats.gpus[0].utilization
                    except:
                        self.system_stats["gpu_usage"] = 0.0

                    # Статус модели
                    self.check_model_status()

                except Exception as e:
                    logging.error(f"Monitoring error: {e}")

                # Планируем следующее обновление через 5 секунд
                if hasattr(self, '_monitor_after_id'):
                    # Отменяем предыдущее задание если есть
                    try:
                        if hasattr(self, 'control_center') and self.control_center and self.control_center.window:
                            self.control_center.window.after_cancel(self._monitor_after_id)
                    except:
                        pass

                # Планируем следующий мониторинг
                try:
                    if hasattr(self, 'control_center') and self.control_center and self.control_center.window:
                        self._monitor_after_id = self.control_center.window.after(5000, monitor)
                except:
                    # Fallback к threading если GUI недоступен
                    threading.Timer(5.0, monitor).start()

        # Запускаем первое обновление
        monitor()
    
    def check_model_status(self):
        """Проверка статуса модели"""
        try:
            if self.backend_type == "lm_studio" and self.llm_adapter:
                status = self.llm_adapter.check_server_status()
                self.system_stats["model_status"] = "running" if status else "offline"
            elif self.backend_type == "ollama":
                response = requests.get("http://localhost:11434/api/tags", timeout=3)
                self.system_stats["model_status"] = "running" if response.status_code == 200 else "offline"
            else:
                self.system_stats["model_status"] = "error"
        except:
            self.system_stats["model_status"] = "offline"
    
    def send_llm_request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Отправка запроса к LLM"""
        start_time = time.time()
        
        try:
            if LM_STUDIO_AVAILABLE and llm_manager:
                result = llm_manager.send_request(prompt, **kwargs)
            else:
                # Fallback к прямому Ollama запросу
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "gpt-oss:20b",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=kwargs.get("timeout", 60)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    result = {
                        "choices": [{"message": {"content": result.get("response", "")}}],
                        "usage": {"total_tokens": len(result.get("response", "").split())},
                        "backend": "ollama"
                    }
                else:
                    result = {"error": f"Ollama error: {response.status_code}"}
            
            response_time = time.time() - start_time
            
            # Логирование взаимодействия
            self.log_model_interaction(prompt, result, response_time)
            
            return result
            
        except Exception as e:
            response_time = time.time() - start_time
            error_result = {"error": str(e)}
            self.log_model_interaction(prompt, error_result, response_time)
            return error_result
    
    def log_model_interaction(self, prompt: str, response: Dict, response_time: float):
        """Логирование взаимодействий с моделью"""
        try:
            response_text = ""
            tokens_used = 0
            status = "success"
            
            if "error" in response:
                status = "error"
                response_text = response["error"]
            elif "choices" in response:
                response_text = response["choices"][0]["message"]["content"]
                tokens_used = response.get("usage", {}).get("total_tokens", 0)
            
            with sqlite3.connect('data/autonomous_gpt.db') as conn:
                conn.execute(
                    "INSERT INTO model_interactions (backend_type, prompt, response, response_time, tokens_used, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (self.backend_type, prompt[:500], response_text[:1000], response_time, tokens_used, status)
                )
                
            # Обновление статистики
            if status == "success":
                self.system_stats["requests_count"] += 1
            else:
                self.system_stats["errors_count"] += 1
                
        except Exception as e:
            logging.error(f"Failed to log model interaction: {e}")


class EmotionalDisplay:
    """Эмоциональное отображение состояния ИИ"""
    
    def __init__(self, server_instance):
        self.server = server_instance
        self.window = None
        self.canvas = None
        self.emotion_state = {
            "happiness": 0.7,
            "curiosity": 0.8,
            "focus": 0.6,
            "energy": 0.5
        }
        
    def create_window(self):
        """Создание окна эмоционального отображения"""
        self.window = tk.Toplevel()
        self.window.title("GPT OSS 20B - Emotional State")
        self.window.geometry("400x300")
        self.window.configure(bg='#000011')
        
        # Canvas для анимации
        self.canvas = tk.Canvas(
            self.window,
            width=380,
            height=280,
            bg='#000011',
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)
        
        self.start_animation()
        
    def start_animation(self):
        """Запуск анимации эмоций"""
        def animate():
            if self.server.running and self.window:
                try:
                    self.update_emotions()
                    self.draw_emotions()
                    # Планируем следующее обновление через tkinter
                    self.window.after(100, animate)
                except Exception as e:
                    logging.error(f"Animation error: {e}")

        # Запускаем анимацию через tkinter's after method
        if self.window:
            self.window.after(100, animate)
    
    def update_emotions(self):
        """Обновление эмоционального состояния"""
        # Влияние системных показателей на эмоции
        cpu = self.server.system_stats["cpu_usage"] / 100.0
        memory = self.server.system_stats["memory_usage"] / 100.0
        
        # Энергия зависит от загрузки CPU
        self.emotion_state["energy"] = 0.3 + cpu * 0.7
        
        # Фокус зависит от использования памяти
        self.emotion_state["focus"] = max(0.2, 1.0 - memory * 0.8)
        
        # Любопытство случайно колеблется
        self.emotion_state["curiosity"] += random.uniform(-0.05, 0.05)
        self.emotion_state["curiosity"] = max(0.1, min(1.0, self.emotion_state["curiosity"]))
        
        # Счастье зависит от статуса модели
        if self.server.system_stats["model_status"] == "running":
            self.emotion_state["happiness"] = min(1.0, self.emotion_state["happiness"] + 0.01)
        else:
            self.emotion_state["happiness"] = max(0.2, self.emotion_state["happiness"] - 0.02)
    
    def draw_emotions(self):
        """Отрисовка эмоционального состояния"""
        if not self.canvas:
            return
            
        self.canvas.delete("all")
        
        width, height = 380, 280
        center_x, center_y = width // 2, height // 2
        
        # Цветовая палитра на основе эмоций
        hue = (self.emotion_state["happiness"] + self.emotion_state["curiosity"]) / 2
        saturation = self.emotion_state["energy"]
        value = self.emotion_state["focus"]
        
        rgb = colorsys.hsv_to_rgb(hue * 0.6, saturation, value)
        color = f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"
        
        # Основная форма (пульсирующий круг)
        pulse = math.sin(time.time() * 2) * 0.1 + 1.0
        radius = 80 * pulse * self.emotion_state["energy"]
        
        self.canvas.create_oval(
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius,
            fill=color, outline="", width=0
        )
        
        # Дополнительные элементы
        for i in range(3):
            angle = time.time() * 0.5 + i * 2.094  # 120 градусов
            x = center_x + math.cos(angle) * 60 * self.emotion_state["curiosity"]
            y = center_y + math.sin(angle) * 60 * self.emotion_state["curiosity"]
            
            self.canvas.create_oval(
                x - 10, y - 10, x + 10, y + 10,
                fill=color, outline="white", width=1
            )
        
        # Информационный текст
        info_text = f"Backend: {self.server.backend_type.title()}\n"
        info_text += f"Model: {self.server.system_stats['model_status']}\n"
        info_text += f"CPU: {self.server.system_stats['cpu_usage']:.1f}%\n"
        info_text += f"Memory: {self.server.system_stats['memory_usage']:.1f}%"
        
        self.canvas.create_text(
            10, 10, text=info_text, 
            anchor="nw", fill="white", font=("Arial", 10)
        )


class ControlCenter:
    """Центр управления автономной системой"""
    
    def __init__(self, server_instance):
        self.server = server_instance
        self.window = None
        
    def create_window(self):
        """Создание окна центра управления"""
        self.window = tk.Tk()
        self.window.title("Autonomous GPT OSS 20B - Control Center")
        self.window.geometry("1000x700")
        self.window.configure(bg='#1e1e1e')
        
        # Настройка стилей
        style = ttk.Style()
        style.theme_use('clam')

        # Создание основного интерфейса
        self.create_main_interface()

    def create_main_interface(self):
        """Создание основного интерфейса управления"""
        # Создание вкладок
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладка статистики
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="System Stats")

        # Вкладка управления
        control_frame = ttk.Frame(notebook)
        notebook.add(control_frame, text="Control")

        # Базовые элементы управления
        ttk.Button(control_frame, text="Start Server",
                  command=self.start_server).pack(pady=5)
        ttk.Button(control_frame, text="Stop Server",
                  command=self.stop_server).pack(pady=5)

    def start_server(self):
        """Запуск сервера"""
        if not self.server.running:
            self.server.running = True
            self.server.start_monitoring()

    def stop_server(self):
        """Остановка сервера"""
        self.server.running = False


# Проверка дополнительных модулей
try:
    from enhanced_gpt_system import EnhancedLMStudioAdapter, EnhancedControlCenter
    ENHANCED_AVAILABLE = True
except ImportError:
    ENHANCED_AVAILABLE = False

# Импорт расширенных модулей
ENHANCED_FEATURES_AVAILABLE = False
try:
    from fixed_web_access import SafeWebAccess
    from fixed_content_policy import AdaptiveContentPolicy
    ENHANCED_FEATURES_AVAILABLE = True
    print("✅ Enhanced features loaded successfully")
except ImportError as e:
    print(f"⚠️ Enhanced features not available: {e}")
    print("   System will work in basic mode")
except Exception as e:
    print(f"⚠️ Enhanced features error: {e}")
    print("   System will work in basic mode")

class EnhancedGPTServer:
    """Расширенная версия автономного GPT сервера"""
    
    def __init__(self, base_server):
        self.base_server = base_server
        
        # Инициализация расширенных модулей
        if ENHANCED_FEATURES_AVAILABLE:
            try:
                self.web_access = SafeWebAccess()
                self.content_policy = AdaptiveContentPolicy()
                self.enhanced_available = True
                print("🌐 Web access and content policy initialized")
            except Exception as e:
                print(f"❌ Failed to initialize enhanced modules: {e}")
                self.enhanced_available = False
                self.web_access = None
                self.content_policy = None
        else:
            self.enhanced_available = False
            self.web_access = None
            self.content_policy = None
        
        # Настройки
        self.web_enabled = False
        self.content_filtering_enabled = True
    
    def send_enhanced_request(self, messages, **kwargs):
        """Отправка запроса с расширенными возможностями"""
        try:
            # Получаем последнее сообщение пользователя
            user_message = ""
            if messages and isinstance(messages, list) and len(messages) > 0:
                last_msg = messages[-1]
                if isinstance(last_msg, dict) and "content" in last_msg:
                    user_message = last_msg["content"]
            
            # Проверка контента если включена фильтрация
            if self.content_filtering_enabled and self.content_policy:
                content_check = self.content_policy.evaluate_content(user_message)
                
                if not content_check.get("allowed", True):
                    return {
                        "error": "Content blocked by policy",
                        "reason": content_check.get("block_reason", "Content policy violation"),
                        "policy_level": content_check.get("policy_level", "unknown")
                    }
            
            # Проверяем нужен ли веб-поиск
            needs_web_search = self.web_enabled and self.should_use_web_search(user_message)
            
            # Выполняем веб-поиск если нужно
            web_context = None
            if needs_web_search and self.web_access:
                try:
                    search_query = self.web_access.extract_search_query(user_message)
                    web_results = self.web_access.search_web_safely(search_query, max_results=3)
                    
                    if web_results.get("success") and web_results.get("results"):
                        web_context = self.format_web_results(web_results["results"])
                        
                        # Добавляем контекст в сообщения
                        enhanced_messages = messages.copy()
                        enhanced_messages.insert(-1, {
                            "role": "system",
                            "content": f"Актуальная информация из интернета:\n{web_context}"
                        })
                        messages = enhanced_messages
                        
                except Exception as e:
                    print(f"Web search error: {e}")
                    # Продолжаем без веб-контекста
            
            # Отправляем запрос к базовому серверу
            result = self.base_server.send_llm_request(user_message, **kwargs)
            
            # Добавляем метаданные
            if isinstance(result, dict):
                result["enhanced"] = {
                    "web_search_used": needs_web_search and web_context is not None,
                    "content_filtered": self.content_filtering_enabled,
                    "policy_level": self.content_policy.current_level if self.content_policy else "none"
                }
            
            return result
            
        except Exception as e:
            print(f"Enhanced request error: {e}")
            return {"error": f"Enhanced request failed: {e}"}
    
    def should_use_web_search(self, message):
        """Проверяет нужен ли веб-поиск"""
        if not message:
            return False
        
        web_triggers = [
            'найди в интернете', 'поищи информацию', 'что нового', 'последние новости',
            'актуальная информация', 'search online', 'look up', 'latest', 'current'
        ]
        
        message_lower = message.lower()
        return any(trigger in message_lower for trigger in web_triggers)
    
    def format_web_results(self, results):
        """Форматирует результаты веб-поиска"""
        if not results:
            return ""
        
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"""
Источник {i}: {result.get('title', 'Без названия')}
URL: {result.get('url', '')}
Содержание: {result.get('content', result.get('snippet', ''))[:500]}...
""")
        
        return "\n".join(formatted)
    
    def toggle_web_access(self, enabled):
        """Переключение веб-доступа"""
        if not self.enhanced_available:
            return False, "Enhanced features not available"
        
        self.web_enabled = enabled
        status = "enabled" if enabled else "disabled"
        print(f"🌐 Web access {status}")
        return True, f"Web access {status}"
    
    def set_content_policy_level(self, level, auth_token=None):
        """Установка уровня контентной политики"""
        if not self.enhanced_available or not self.content_policy:
            return False, "Content policy not available"
        
        try:
            success = self.content_policy.set_policy_level(level, auth_token, "Manual change")
            if success:
                return True, f"Content policy set to {level}"
            else:
                return False, "Failed to change policy level (check authorization)"
        except Exception as e:
            return False, f"Error changing policy: {e}"
    
    def get_enhanced_status(self):
        """Получение статуса расширенных функций"""
        status = {
            "enhanced_available": self.enhanced_available,
            "web_enabled": self.web_enabled,
            "content_filtering_enabled": self.content_filtering_enabled
        }
        
        if self.content_policy:
            status["content_policy_level"] = self.content_policy.current_level
            
        if self.web_access:
            try:
                web_stats = self.web_access.get_usage_statistics()
                status["web_statistics"] = web_stats
            except:
                status["web_statistics"] = {"error": "Failed to get stats"}
        
        return status


class SimpleEnhancedControlCenter:
    """Простой интерфейс управления расширенными функциями"""
    
    def __init__(self, enhanced_server):
        self.enhanced_server = enhanced_server
        self.window = None
    
    def create_simple_window(self):
        """Создание простого окна управления"""
        self.window = tk.Toplevel()
        self.window.title("Enhanced GPT OSS 20B - Simple Control")
        self.window.geometry("600x400")
        
        # Основная информация
        info_frame = ttk.LabelFrame(self.window, text="Enhanced Features Status")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.status_text = scrolledtext.ScrolledText(info_frame, height=15)
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Кнопки управления
        control_frame = ttk.Frame(self.window)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="Refresh Status", 
                  command=self.refresh_status).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Toggle Web Access", 
                  command=self.toggle_web).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Test Web Search", 
                  command=self.test_web_search).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="Safe Mode", 
                  command=self.set_safe_mode).pack(side=tk.LEFT, padx=5)
        
        # Изначальное обновление статуса
        self.refresh_status()
    
    def refresh_status(self):
        """Обновление статуса"""
        try:
            status = self.enhanced_server.get_enhanced_status()
            
            status_text = "Enhanced GPT OSS 20B - Status Report\n"
            status_text += "=" * 50 + "\n\n"
            status_text += f"Enhanced Features: {'Available' if status['enhanced_available'] else 'Not Available'}\n"
            status_text += f"Web Access: {'Enabled' if status['web_enabled'] else 'Disabled'}\n"
            status_text += f"Content Filtering: {'Enabled' if status['content_filtering_enabled'] else 'Disabled'}\n"
            
            if 'content_policy_level' in status:
                status_text += f"Content Policy Level: {status['content_policy_level']}\n"
            
            status_text += f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            if 'web_statistics' in status and 'error' not in status['web_statistics']:
                web_stats = status['web_statistics']
                status_text += f"Web Statistics (24h):\n"
                status_text += f"  Total Requests: {web_stats.get('total_requests', 0)}\n"
                status_text += f"  Success Rate: {web_stats.get('success_rate', 0):.1%}\n"
                status_text += f"  Blocked Attempts: {web_stats.get('blocked_attempts', 0)}\n\n"
            
            # Инструкции по использованию
            status_text += "Usage Instructions:\n"
            status_text += "-" * 20 + "\n"
            status_text += "• Use 'найди в интернете' or 'search online' to trigger web search\n"
            status_text += "• Web access is disabled by default for security\n"
            status_text += "• Content filtering is always active\n"
            status_text += "• Use 'Safe Mode' to reset all settings\n\n"
            
            status_text += "Available Commands:\n"
            status_text += "-" * 20 + "\n"
            status_text += "• 'найди в интернете последние новости об ИИ'\n"
            status_text += "• 'search online for Python tutorials'\n"
            status_text += "• 'что нового в области машинного обучения'\n"
            
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', status_text)
            
        except Exception as e:
            error_text = f"Error updating status: {e}\n"
            error_text += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', error_text)
    
    def toggle_web(self):
        """Переключение веб-доступа"""
        try:
            current_status = self.enhanced_server.get_enhanced_status()
            new_state = not current_status.get('web_enabled', False)
            
            success, message = self.enhanced_server.toggle_web_access(new_state)
            
            if success:
                messagebox.showinfo("Web Access", message)
            else:
                messagebox.showerror("Error", message)
            
            self.refresh_status()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle web access: {e}")
    
    def test_web_search(self):
        """Тестирование веб-поиска"""
        if not self.enhanced_server.enhanced_available:
            messagebox.showerror("Error", "Enhanced features not available")
            return
        
        # Простой тест
        test_message = "найди в интернете информацию о Python"
        
        try:
            # Временно включаем веб-доступ для теста
            old_web_state = self.enhanced_server.web_enabled
            self.enhanced_server.web_enabled = True
            
            messages = [{"role": "user", "content": test_message}]
            result = self.enhanced_server.send_enhanced_request(messages)
            
            # Восстанавливаем предыдущее состояние
            self.enhanced_server.web_enabled = old_web_state
            
            if "error" in result:
                messagebox.showerror("Test Failed", f"Web search test failed: {result['error']}")
            else:
                enhanced_info = result.get("enhanced", {})
                web_used = enhanced_info.get("web_search_used", False)
                
                test_result = f"Web Search Test Results:\n\n"
                test_result += f"Web search triggered: {web_used}\n"
                test_result += f"Response received: {'Yes' if 'choices' in result else 'No'}\n"
                
                if 'choices' in result and result['choices']:
                    response_preview = result['choices'][0]['message']['content'][:200]
                    test_result += f"Response preview: {response_preview}...\n"
                
                messagebox.showinfo("Test Results", test_result)
            
        except Exception as e:
            messagebox.showerror("Test Error", f"Web search test error: {e}")
    
    def set_safe_mode(self):
        """Установка безопасного режима"""
        try:
            # Отключаем веб-доступ
            self.enhanced_server.web_enabled = False
            
            # Устанавливаем безопасный уровень контента
            if self.enhanced_server.content_policy:
                self.enhanced_server.content_policy.set_policy_level("safe", reason="Manual safe mode")
            
            self.refresh_status()
            messagebox.showinfo("Safe Mode", "System reset to safe mode:\n• Web access disabled\n• Content policy set to safe")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set safe mode: {e}")
    
    def show(self):
        """Показать окно"""
        if self.window is None or not self.window.winfo_exists():
            self.create_simple_window()
        else:
            self.window.lift()
            self.window.focus_set()


# Интеграция расширенных функций
def integrate_enhanced_features(existing_server):
    """Интеграция с существующим сервером"""
    if not ENHANCED_FEATURES_AVAILABLE:
        print("⚠️ Enhanced features not available, skipping integration")
        return existing_server

    try:
        # Создаем расширенную версию
        enhanced_server = EnhancedGPTServer(existing_server)

        # Добавляем новые методы к существующему серверу
        existing_server.enhanced = enhanced_server
        existing_server.send_enhanced_request = enhanced_server.send_enhanced_request
        existing_server.get_enhanced_status = enhanced_server.get_enhanced_status
        existing_server.toggle_web_access = enhanced_server.toggle_web_access
        existing_server.set_content_policy_level = enhanced_server.set_content_policy_level

        print("✅ Enhanced features integrated successfully")

        # Создаем простой интерфейс управления
        control_center = SimpleEnhancedControlCenter(enhanced_server)

        # Добавляем кнопку в основной интерфейс (если есть)
        try:
            def show_enhanced_control():
                control_center.show()

            existing_server.show_enhanced_control = show_enhanced_control
            print("🎮 Enhanced control center available")

        except Exception as e:
            print(f"⚠️ Could not integrate control center: {e}")

        return existing_server

    except Exception as e:
        print(f"❌ Failed to integrate enhanced features: {e}")
        return existing_server


print("📋 Enhanced features integration module loaded")
print("💡 Add the integration code to your main() function to enable enhanced features")


def main():
    """Основная функция запуска"""
    print("🚀 Starting Autonomous GPT OSS 20B Server...")

    try:
        # Создание основного сервера
        server = AutonomousGPTServer()
        server.running = True

        # Интеграция расширенных функций
        server = integrate_enhanced_features(server)

        # Создание GUI сначала (в основном потоке)
        server.control_center = ControlCenter(server)
        server.control_center.create_window()

        server.emotional_display = EmotionalDisplay(server)
        server.emotional_display.create_window()

        print("✅ GUI created successfully")

        # Теперь запускаем мониторинг (после создания GUI)
        server.start_monitoring()

        print("✅ Server started successfully")
        print("🎮 Control Center and Emotional Display are running")

        # Показать расширенный интерфейс управления если доступен
        if hasattr(server, 'show_enhanced_control'):
            try:
                server.show_enhanced_control()
            except Exception as e:
                print(f"⚠️ Enhanced control not available: {e}")

        # Запуск главного цикла
        server.control_center.window.mainloop()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        logging.error(f"Server startup error: {e}")
    finally:
        if 'server' in locals():
            server.running = False
        print("👋 Server stopped")


if __name__ == "__main__":
    main()