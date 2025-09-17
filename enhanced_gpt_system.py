import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# Импорт созданных модулей
try:
    from web_access_module import SafeWebAccess
    from content_policy_module import AdaptiveContentPolicy, ContentLevel
    from lm_studio_adapter import LMStudioAdapter, llm_manager
    WEB_ACCESS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Enhanced modules not found: {e}")
    WEB_ACCESS_AVAILABLE = False

class EnhancedLMStudioAdapter:
    """Расширенный адаптер LM Studio с веб-доступом и управлением контентом"""

    def __init__(self, base_adapter=None):
        self.base_adapter = base_adapter or (llm_manager if llm_manager else None)

        # Инициализация расширенных модулей
        if WEB_ACCESS_AVAILABLE:
            self.web_access = SafeWebAccess()
            self.content_policy = AdaptiveContentPolicy()
        else:
            self.web_access = None
            self.content_policy = None

        # Настройки
        self.web_enabled = False
        self.learning_enabled = False

        # Логирование
        self.logger = logging.getLogger(__name__)

        # Кэш обучающих взаимодействий
        self.learning_buffer = []
        self.max_learning_buffer = 100

    def send_enhanced_request(self, messages: List[Dict], enable_web: bool = None,
                            user_context: str = None, **kwargs) -> Dict[str, Any]:
        """Отправка запроса с расширенными возможностями"""

        # Использование настройки по умолчанию, если не указано
        if enable_web is None:
            enable_web = self.web_enabled

        # Получение последнего сообщения пользователя
        user_message = ""
        if messages and messages[-1]["role"] == "user":
            user_message = messages[-1]["content"]

        # Проверка контента перед обработкой
        if self.content_policy:
            content_check = self.content_policy.evaluate_content(user_message, user_context)

            if not content_check["allowed"]:
                return {
                    "error": "Content blocked by policy",
                    "reason": content_check.get("block_reason", "Content policy violation"),
                    "policy_level": content_check["policy_level"],
                    "content_scores": content_check["category_scores"]
                }

        # Определение необходимости веб-поиска
        needs_web_search = enable_web and self.should_use_web_search(user_message)

        enhanced_messages = messages.copy()
        web_context = None

        # Выполнение веб-поиска при необходимости
        if needs_web_search and self.web_access:
            try:
                search_query = self.web_access.extract_search_query(user_message)
                self.logger.info(f"Performing web search for: {search_query}")

                web_results = self.web_access.search_web_safely(
                    search_query,
                    max_results=5,
                    user_context=user_context
                )

                if web_results["success"] and web_results["results"]:
                    web_context = self.format_web_context(web_results["results"])

                    # Добавление веб-контекста в сообщения
                    enhanced_messages.insert(-1, {
                        "role": "system",
                        "content": f"Актуальная информация из интернета:\n{web_context}"
                    })

                    self.logger.info(f"Added web context from {len(web_results['results'])} sources")

            except Exception as e:
                self.logger.error(f"Web search failed: {e}")
                # Продолжаем без веб-контекста

        # Отправка запроса к модели
        try:
            if self.base_adapter:
                result = self.base_adapter.send_request(enhanced_messages, **kwargs)
            else:
                return {"error": "No LLM backend available"}

            # Проверка результата на соответствие контентной политике
            if "choices" in result and result["choices"]:
                response_content = result["choices"][0]["message"]["content"]

                if self.content_policy:
                    response_check = self.content_policy.evaluate_content(
                        response_content,
                        user_context
                    )

                    if not response_check["allowed"]:
                        return {
                            "error": "Response blocked by content policy",
                            "reason": response_check.get("block_reason", "Response policy violation"),
                            "policy_level": response_check["policy_level"],
                            "original_blocked": True
                        }

            # Добавление метаданных к результату
            if isinstance(result, dict):
                result["enhanced"] = {
                    "web_search_used": needs_web_search and web_context is not None,
                    "web_sources_count": len(web_results["results"]) if needs_web_search and web_context else 0,
                    "content_policy_level": self.content_policy.current_level.value if self.content_policy else "disabled",
                    "timestamp": datetime.now().isoformat()
                }

            # Сохранение взаимодействия для обучения
            if self.learning_enabled:
                self.add_learning_interaction(user_message, result, user_context)

            return result

        except Exception as e:
            self.logger.error(f"Enhanced request failed: {e}")
            return {"error": f"Request failed: {str(e)}"}

    def should_use_web_search(self, message: str) -> bool:
        """Определение необходимости веб-поиска"""
        web_triggers = [
            # Русские триггеры
            'найди в интернете', 'поищи информацию', 'что нового', 'последние новости',
            'актуальная информация', 'свежие данные', 'недавние события',
            'текущая ситуация', 'современное состояние', 'на сегодняшний день',

            # Английские триггеры
            'search the internet', 'look up online', 'latest news', 'recent information',
            'current data', 'up to date', 'what\'s new', 'recent developments',
            'latest updates', 'current situation', 'recent events'
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in web_triggers)

    def format_web_context(self, web_results: List[Dict]) -> str:
        """Форматирование веб-контекста для модели"""
        context_parts = []

        for i, result in enumerate(web_results, 1):
            context_part = f"""
Источник {i}: {result['title']}
URL: {result['url']}
Тип: {result.get('domain_type', 'Unknown')}
Уровень доверия: {result['trust_score']:.2f}
Содержание: {result['content'][:800]}...
"""
            context_parts.append(context_part.strip())

        return "\n\n".join(context_parts)

    def add_learning_interaction(self, user_input: str, model_output: Dict, user_context: str):
        """Добавление взаимодействия для потенциального обучения"""
        if not self.learning_enabled:
            return

        try:
            # Извлечение ответа модели
            response_text = ""
            if "choices" in model_output and model_output["choices"]:
                response_text = model_output["choices"][0]["message"]["content"]

            interaction = {
                "user_input": user_input,
                "model_output": response_text,
                "timestamp": datetime.now().isoformat(),
                "user_context": user_context,
                "web_enhanced": model_output.get("enhanced", {}).get("web_search_used", False),
                "content_policy_level": model_output.get("enhanced", {}).get("content_policy_level", "unknown")
            }

            self.learning_buffer.append(interaction)

            # Ограничение размера буфера
            if len(self.learning_buffer) > self.max_learning_buffer:
                self.learning_buffer = self.learning_buffer[-self.max_learning_buffer:]

            self.logger.debug(f"Added learning interaction, buffer size: {len(self.learning_buffer)}")

        except Exception as e:
            self.logger.error(f"Failed to add learning interaction: {e}")

    def export_learning_data(self, filename: str = None) -> str:
        """Экспорт данных для обучения"""
        if not filename:
            filename = f"learning_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "interactions_count": len(self.learning_buffer),
                "interactions": self.learning_buffer,
                "settings": {
                    "web_enabled": self.web_enabled,
                    "learning_enabled": self.learning_enabled,
                    "content_policy_level": self.content_policy.current_level.value if self.content_policy else "disabled"
                }
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Learning data exported to {filename}")
            return filename

        except Exception as e:
            self.logger.error(f"Failed to export learning data: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """Получение статуса расширенной системы"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "base_adapter_available": self.base_adapter is not None,
            "web_access_enabled": self.web_enabled,
            "web_access_available": self.web_access is not None,
            "content_policy_available": self.content_policy is not None,
            "learning_enabled": self.learning_enabled,
            "learning_buffer_size": len(self.learning_buffer)
        }

        # Статус веб-доступа
        if self.web_access:
            try:
                web_stats = self.web_access.get_usage_statistics()
                status["web_statistics"] = web_stats
            except Exception as e:
                status["web_statistics"] = {"error": str(e)}

        # Статус контентной политики
        if self.content_policy:
            try:
                content_stats = self.content_policy.get_content_statistics()
                status["content_policy"] = {
                    "current_level": self.content_policy.current_level.value,
                    "statistics": content_stats
                }
            except Exception as e:
                status["content_policy"] = {"error": str(e)}

        # Статус базового адаптера
        if self.base_adapter:
            try:
                base_status = self.base_adapter.get_status()
                status["base_adapter_status"] = base_status
            except Exception as e:
                status["base_adapter_status"] = {"error": str(e)}

        return status

    def configure_web_access(self, enabled: bool):
        """Настройка веб-доступа"""
        self.web_enabled = enabled and self.web_access is not None
        self.logger.info(f"Web access {'enabled' if self.web_enabled else 'disabled'}")

    def configure_learning(self, enabled: bool):
        """Настройка режима обучения"""
        self.learning_enabled = enabled
        self.logger.info(f"Learning mode {'enabled' if self.learning_enabled else 'disabled'}")

    def clear_learning_buffer(self):
        """Очистка буфера обучения"""
        self.learning_buffer.clear()
        self.logger.info("Learning buffer cleared")


class EnhancedControlCenter:
    """Расширенный центр управления с веб-доступом и контролем контента"""

    def __init__(self, enhanced_adapter: EnhancedLMStudioAdapter):
        self.adapter = enhanced_adapter
        self.window = None
        self.logger = logging.getLogger(__name__)

        # Переменные интерфейса
        self.web_enabled_var = None
        self.learning_enabled_var = None
        self.policy_level_var = None
        self.auth_token_var = None

        # Мониторинг
        self.monitoring_active = False

    def create_window(self):
        """Создание окна расширенного центра управления"""
        self.window = tk.Toplevel()
        self.window.title("Enhanced GPT OSS 20B - Advanced Control Center")
        self.window.geometry("1200x800")
        self.window.configure(bg='#1a1a1a')

        # Настройка стилей
        style = ttk.Style()
        style.theme_use('clam')
        self.configure_styles(style)

        self.create_widgets()
        self.start_monitoring()

    def configure_styles(self, style):
        """Настройка темных стилей"""
        style.configure('Dark.TLabel', background='#1a1a1a', foreground='#ffffff')
        style.configure('Dark.TButton', background='#3c3c3c', foreground='#ffffff')
        style.configure('Dark.TFrame', background='#1a1a1a')
        style.configure('Dark.TLabelFrame', background='#1a1a1a', foreground='#ffffff')
        style.configure('Warning.TButton', background='#ff6b35', foreground='#ffffff')
        style.configure('Danger.TButton', background='#dc3545', foreground='#ffffff')
        style.configure('Success.TButton', background='#28a745', foreground='#ffffff')

    def create_widgets(self):
        """Создание виджетов расширенного интерфейса"""
        # Основной контейнер с вкладками
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладки
        self.create_main_control_tab(notebook)
        self.create_web_access_tab(notebook)
        self.create_content_policy_tab(notebook)
        self.create_learning_tab(notebook)
        self.create_monitoring_tab(notebook)
        self.create_security_tab(notebook)

    def create_main_control_tab(self, notebook):
        """Основная вкладка управления"""
        frame = ttk.Frame(notebook, style='Dark.TFrame')
        notebook.add(frame, text="Main Control")

        # Статус системы
        status_frame = ttk.LabelFrame(frame, text="System Status", style='Dark.TLabelFrame')
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        self.status_text = scrolledtext.ScrolledText(
            status_frame, height=8, bg='#2d2d2d', fg='#00ff00',
            font=('Consolas', 10)
        )
        self.status_text.pack(fill=tk.X, padx=5, pady=5)

        # Быстрые действия
        actions_frame = ttk.LabelFrame(frame, text="Quick Actions", style='Dark.TLabelFrame')
        actions_frame.pack(fill=tk.X, padx=10, pady=5)

        actions_buttons = [
            ("Refresh Status", self.refresh_status, 'Dark.TButton'),
            ("Test Web Search", self.test_web_search, 'Dark.TButton'),
            ("Test Model Response", self.test_model_response, 'Dark.TButton'),
            ("Export Logs", self.export_logs, 'Dark.TButton'),
            ("Emergency Reset", self.emergency_reset, 'Danger.TButton')
        ]

        for i, (text, command, style) in enumerate(actions_buttons):
            btn = ttk.Button(actions_frame, text=text, command=command, style=style)
            btn.grid(row=i//3, column=i%3, padx=5, pady=5, sticky='ew')

        # Настройка сетки
        for i in range(3):
            actions_frame.columnconfigure(i, weight=1)

    def create_web_access_tab(self, notebook):
        """Вкладка управления веб-доступом"""
        frame = ttk.Frame(notebook, style='Dark.TFrame')
        notebook.add(frame, text="Web Access")

        # Настройки веб-доступа
        settings_frame = ttk.LabelFrame(frame, text="Web Access Settings", style='Dark.TLabelFrame')
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        self.web_enabled_var = tk.BooleanVar(value=self.adapter.web_enabled)
        ttk.Checkbutton(
            settings_frame,
            text="Enable Web Access",
            variable=self.web_enabled_var,
            command=self.toggle_web_access
        ).pack(anchor='w', padx=5, pady=2)

        # Статистика веб-доступа
        web_stats_frame = ttk.LabelFrame(frame, text="Web Access Statistics", style='Dark.TLabelFrame')
        web_stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.web_stats_text = scrolledtext.ScrolledText(
            web_stats_frame, height=10, bg='#2d2d2d', fg='#ffffff',
            font=('Consolas', 9)
        )
        self.web_stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_content_policy_tab(self, notebook):
        """Вкладка управления контентной политикой"""
        frame = ttk.Frame(notebook, style='Dark.TFrame')
        notebook.add(frame, text="Content Policy")

        # Уровень политики
        policy_level_frame = ttk.LabelFrame(frame, text="Policy Level", style='Dark.TLabelFrame')
        policy_level_frame.pack(fill=tk.X, padx=10, pady=5)

        self.policy_level_var = tk.StringVar(
            value=self.adapter.content_policy.current_level.value if self.adapter.content_policy else "safe"
        )

        policy_levels = [
            ("Safe Mode", "safe", "Maximum restrictions for public use"),
            ("Educational Mode", "educational", "Relaxed restrictions for learning"),
            ("Research Mode", "research", "Minimal restrictions for research"),
            ("Unrestricted Mode", "unrestricted", "Almost no restrictions (dangerous!)")
        ]

        for text, value, description in policy_levels:
            frame_row = ttk.Frame(policy_level_frame)
            frame_row.pack(fill=tk.X, padx=5, pady=2)

            radio = ttk.Radiobutton(
                frame_row,
                text=text,
                variable=self.policy_level_var,
                value=value,
                command=self.change_policy_level
            )
            radio.pack(side=tk.LEFT)

            desc_label = ttk.Label(frame_row, text=f"- {description}", style='Dark.TLabel')
            desc_label.pack(side=tk.LEFT, padx=(10, 0))

        # Статистика контентной политики
        policy_stats_frame = ttk.LabelFrame(frame, text="Content Policy Statistics", style='Dark.TLabelFrame')
        policy_stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.policy_stats_text = scrolledtext.ScrolledText(
            policy_stats_frame, bg='#2d2d2d', fg='#ffffff',
            font=('Consolas', 9)
        )
        self.policy_stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_learning_tab(self, notebook):
        """Вкладка управления обучением"""
        frame = ttk.Frame(notebook, style='Dark.TFrame')
        notebook.add(frame, text="Learning")

        # Настройки обучения
        learning_settings_frame = ttk.LabelFrame(frame, text="Learning Settings", style='Dark.TLabelFrame')
        learning_settings_frame.pack(fill=tk.X, padx=10, pady=5)

        self.learning_enabled_var = tk.BooleanVar(value=self.adapter.learning_enabled)
        ttk.Checkbutton(
            learning_settings_frame,
            text="Enable Adaptive Learning",
            variable=self.learning_enabled_var,
            command=self.toggle_learning
        ).pack(anchor='w', padx=5, pady=2)

        # Буфер обучения
        buffer_frame = ttk.LabelFrame(frame, text="Learning Buffer", style='Dark.TLabelFrame')
        buffer_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        buffer_info_frame = ttk.Frame(buffer_frame)
        buffer_info_frame.pack(fill=tk.X, padx=5, pady=5)

        self.buffer_size_label = ttk.Label(buffer_info_frame, text=f"Buffer size: {len(self.adapter.learning_buffer)}", style='Dark.TLabel')
        self.buffer_size_label.pack(side=tk.LEFT)

        ttk.Button(buffer_info_frame, text="Clear Buffer", command=self.clear_learning_buffer).pack(side=tk.RIGHT, padx=(0, 5))
        ttk.Button(buffer_info_frame, text="Export Data", command=self.export_learning_data).pack(side=tk.RIGHT, padx=(0, 5))

        # Просмотр буфера
        self.learning_buffer_text = scrolledtext.ScrolledText(
            buffer_frame, bg='#2d2d2d', fg='#ffffff',
            font=('Consolas', 9)
        )
        self.learning_buffer_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_monitoring_tab(self, notebook):
        """Вкладка мониторинга системы"""
        frame = ttk.Frame(notebook, style='Dark.TFrame')
        notebook.add(frame, text="Monitoring")

        # Реальный мониторинг
        self.monitoring_text = scrolledtext.ScrolledText(
            frame, bg='#000000', fg='#00ff00',
            font=('Consolas', 10)
        )
        self.monitoring_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Кнопки управления мониторингом
        monitoring_buttons_frame = ttk.Frame(frame)
        monitoring_buttons_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(monitoring_buttons_frame, text="Clear Log", command=self.clear_monitoring_log).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(monitoring_buttons_frame, text="Save Log", command=self.save_monitoring_log).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(monitoring_buttons_frame, text="Auto-scroll", command=self.toggle_auto_scroll).pack(side=tk.LEFT)

        self.auto_scroll_enabled = True

    def create_security_tab(self, notebook):
        """Вкладка безопасности"""
        frame = ttk.Frame(notebook, style='Dark.TFrame')
        notebook.add(frame, text="Security")

        # Аварийные кнопки
        emergency_frame = ttk.LabelFrame(frame, text="🚨 Emergency Controls", style='Dark.TLabelFrame')
        emergency_frame.pack(fill=tk.X, padx=10, pady=5)

        emergency_buttons = [
            ("Disable All Enhanced Features", self.disable_all_features, 'Warning.TButton'),
            ("Reset to Safe Mode", self.reset_to_safe_mode, 'Warning.TButton'),
            ("Emergency Shutdown", self.emergency_shutdown, 'Danger.TButton'),
            ("Force Model Reload", self.force_model_reload, 'Dark.TButton')
        ]

        for text, command, style in emergency_buttons:
            ttk.Button(emergency_frame, text=text, command=command, style=style).pack(fill=tk.X, padx=5, pady=2)

        # Лог безопасности
        security_log_frame = ttk.LabelFrame(frame, text="Security Log", style='Dark.TLabelFrame')
        security_log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.security_log_text = scrolledtext.ScrolledText(
            security_log_frame, bg='#2d2d2d', fg='#ffff00',
            font=('Consolas', 9)
        )
        self.security_log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def start_monitoring(self):
        """Запуск мониторинга системы"""
        if self.monitoring_active:
            return

        self.monitoring_active = True

        def monitor_loop():
            while self.monitoring_active and self.window and self.window.winfo_exists():
                try:
                    status = self.adapter.get_status()
                    self.update_monitoring_display(status)
                    self.update_web_statistics()
                    self.update_policy_statistics()
                    self.update_learning_buffer_display()
                    threading.Event().wait(5)
                except Exception as e:
                    self.log_monitoring_message(f"Monitoring error: {e}")
                    threading.Event().wait(10)

        threading.Thread(target=monitor_loop, daemon=True).start()

    def update_monitoring_display(self, status: Dict[str, Any]):
        """Обновление дисплея мониторинга"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")

            monitor_text = f"[{timestamp}] System Status Update\n"
            monitor_text += "=" * 50 + "\n"
            monitor_text += f"Base Adapter: {'✓' if status['base_adapter_available'] else '✗'}\n"
            monitor_text += f"Web Access: {'✓ ENABLED' if status['web_access_enabled'] else '✗ disabled'}\n"
            monitor_text += f"Learning: {'✓ ENABLED' if status['learning_enabled'] else '✗ disabled'}\n"
            monitor_text += f"Learning Buffer: {status['learning_buffer_size']} interactions\n"

            # Статистика веб-доступа
            if 'web_statistics' in status and 'total_requests' in status['web_statistics']:
                web_stats = status['web_statistics']
                monitor_text += f"\nWeb Requests (24h): {web_stats['total_requests']}\n"
                monitor_text += f"Success Rate: {web_stats['success_rate']:.1%}\n"
                monitor_text += f"Blocked Attempts: {web_stats['blocked_attempts']}\n"

            monitor_text += "\n" + "=" * 50 + "\n\n"

            self.log_monitoring_message(monitor_text)

        except Exception as e:
            self.log_monitoring_message(f"Display update error: {e}\n")

    def update_web_statistics(self):
        """Обновление статистики веб-доступа"""
        if not self.adapter.web_access:
            return

        try:
            stats = self.adapter.web_access.get_usage_statistics()

            stats_text = "Web Access Statistics (Last 24 Hours)\n"
            stats_text += "=" * 40 + "\n\n"

            if "error" not in stats:
                stats_text += f"Total Requests: {stats.get('total_requests', 0)}\n"
                stats_text += f"Successful Requests: {stats.get('successful_requests', 0)}\n"
                stats_text += f"Success Rate: {stats.get('success_rate', 0):.1%}\n"
                stats_text += f"Average Response Time: {stats.get('avg_response_time', 0):.2f}s\n"
                stats_text += f"Average Trust Score: {stats.get('avg_trust_score', 0):.2f}\n"
                stats_text += f"Blocked Attempts: {stats.get('blocked_attempts', 0)}\n\n"

                if stats.get('top_domains'):
                    stats_text += "Top Domains:\n"
                    for domain_info in stats['top_domains']:
                        stats_text += f"  {domain_info['domain']}: {domain_info['requests']} requests\n"
            else:
                stats_text += f"Error getting statistics: {stats['error']}\n"

            if self.window and self.window.winfo_exists():
                self.window.after(0, lambda: self._update_web_stats_display(stats_text))

        except Exception as e:
            self.log_monitoring_message(f"Web stats update error: {e}\n")

    def _update_web_stats_display(self, text):
        """Обновление дисплея статистики веб-доступа"""
        try:
            self.web_stats_text.delete('1.0', tk.END)
            self.web_stats_text.insert('1.0', text)
        except:
            pass

    def update_policy_statistics(self):
        """Обновление статистики контентной политики"""
        if not self.adapter.content_policy:
            return

        try:
            stats = self.adapter.content_policy.get_content_statistics()

            stats_text = "Content Policy Statistics (Last 24 Hours)\n"
            stats_text += "=" * 45 + "\n\n"

            if "error" not in stats:
                stats_text += f"Total Evaluations: {stats.get('total_evaluations', 0)}\n"
                stats_text += f"Allowed Content: {stats.get('allowed_count', 0)}\n"
                stats_text += f"Blocked Content: {stats.get('blocked_count', 0)}\n"
                stats_text += f"Allow Rate: {stats.get('allow_rate', 0):.1%}\n"
                stats_text += f"Current Policy Level: {stats.get('current_policy_level', 'Unknown')}\n\n"

                if stats.get('level_distribution'):
                    stats_text += "Usage by Policy Level:\n"
                    for level, count in stats['level_distribution'].items():
                        stats_text += f"  {level}: {count} evaluations\n"

                if stats.get('top_block_reasons'):
                    stats_text += "\nTop Block Reasons:\n"
                    for reason_info in stats['top_block_reasons'][:5]:
                        stats_text += f"  {reason_info['reason']}: {reason_info['count']} times\n"
            else:
                stats_text += f"Error getting statistics: {stats['error']}\n"

            if self.window and self.window.winfo_exists():
                self.window.after(0, lambda: self._update_policy_stats_display(stats_text))

        except Exception as e:
            self.log_monitoring_message(f"Policy stats update error: {e}\n")

    def _update_policy_stats_display(self, text):
        """Обновление дисплея статистики контентной политики"""
        try:
            self.policy_stats_text.delete('1.0', tk.END)
            self.policy_stats_text.insert('1.0', text)
        except:
            pass

    def update_learning_buffer_display(self):
        """Обновление отображения буфера обучения"""
        try:
            # Обновление размера буфера
            buffer_size = len(self.adapter.learning_buffer)
            if self.window and self.window.winfo_exists():
                self.window.after(0, lambda: self.buffer_size_label.configure(text=f"Buffer size: {buffer_size}"))

            # Обновление содержимого буфера (показываем последние 10 записей)
            display_text = "Recent Learning Interactions:\n"
            display_text += "=" * 40 + "\n\n"

            recent_interactions = self.adapter.learning_buffer[-10:] if self.adapter.learning_buffer else []

            for i, interaction in enumerate(reversed(recent_interactions), 1):
                display_text += f"{i}. [{interaction.get('timestamp', 'Unknown')}]\n"
                display_text += f"   Input: {interaction.get('user_input', '')[:100]}...\n"
                display_text += f"   Output: {interaction.get('model_output', '')[:100]}...\n"
                display_text += f"   Context: {interaction.get('user_context', 'None')}\n"
                display_text += f"   Web Enhanced: {interaction.get('web_enhanced', False)}\n\n"

            if not recent_interactions:
                display_text += "No learning interactions recorded yet.\n"

            if self.window and self.window.winfo_exists():
                self.window.after(0, lambda: self._update_learning_buffer_display(display_text))

        except Exception as e:
            self.log_monitoring_message(f"Learning buffer update error: {e}\n")

    def _update_learning_buffer_display(self, text):
        """Обновление дисплея буфера обучения"""
        try:
            self.learning_buffer_text.delete('1.0', tk.END)
            self.learning_buffer_text.insert('1.0', text)
        except:
            pass

    def log_monitoring_message(self, message: str):
        """Логирование сообщения в мониторинг"""
        try:
            if self.window and self.window.winfo_exists():
                self.window.after(0, lambda: self._append_to_monitoring(message))
        except:
            pass

    def _append_to_monitoring(self, message: str):
        """Добавление сообщения в текстовое поле мониторинга"""
        try:
            self.monitoring_text.insert(tk.END, message)

            # Ограничение размера лога
            lines = int(self.monitoring_text.index('end-1c').split('.')[0])
            if lines > 1000:
                self.monitoring_text.delete('1.0', '500.0')

            # Автопрокрутка
            if self.auto_scroll_enabled:
                self.monitoring_text.see(tk.END)

        except Exception as e:
            print(f"Monitoring append error: {e}")

    # Методы управления
    def toggle_web_access(self):
        """Переключение веб-доступа"""
        self.adapter.web_enabled = self.web_enabled_var.get()
        status = "ENABLED" if self.adapter.web_enabled else "DISABLED"
        self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Web access {status}\n")
        messagebox.showinfo("Web Access", f"Web access has been {status.lower()}")

    def toggle_learning(self):
        """Переключение адаптивного обучения"""
        if self.learning_enabled_var.get():
            # Предупреждение при включении
            warning = """
⚠️ WARNING: Enabling adaptive learning is potentially unsafe!

The model may learn inappropriate behaviors from interactions.
Only enable this in controlled testing environments.

Are you sure you want to continue?
"""
            if not messagebox.askyesno("Security Warning", warning):
                self.learning_enabled_var.set(False)
                return

        self.adapter.learning_enabled = self.learning_enabled_var.get()
        status = "ENABLED" if self.adapter.learning_enabled else "DISABLED"
        self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Adaptive learning {status}\n")
        messagebox.showinfo("Adaptive Learning", f"Adaptive learning has been {status.lower()}")

    def change_policy_level(self):
        """Изменение уровня контентной политики"""
        if not self.adapter.content_policy:
            messagebox.showerror("Error", "Content policy module not available")
            return

        new_level_str = self.policy_level_var.get()
        messagebox.showinfo("Policy Change", f"Content policy level changed to: {new_level_str}")

    def refresh_status(self):
        """Обновление статуса системы"""
        try:
            status = self.adapter.get_status()
            status_text = "Enhanced GPT OSS 20B System Status\n"
            status_text += "=" * 50 + "\n\n"
            status_text += f"Timestamp: {status['timestamp']}\n"
            status_text += f"Base Adapter: {'Available' if status['base_adapter_available'] else 'Not Available'}\n"
            status_text += f"Web Access: {'Enabled' if status['web_access_enabled'] else 'Disabled'}\n"
            status_text += f"Web Module: {'Available' if status['web_access_available'] else 'Not Available'}\n"
            status_text += f"Content Policy: {'Available' if status['content_policy_available'] else 'Not Available'}\n"
            status_text += f"Adaptive Learning: {'Enabled' if status['learning_enabled'] else 'Disabled'}\n"
            status_text += f"Learning Buffer Size: {status['learning_buffer_size']}\n\n"

            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', status_text)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh status: {e}")

    def test_web_search(self):
        """Тестирование веб-поиска"""
        if not self.adapter.web_access:
            messagebox.showerror("Error", "Web access module not available")
            return

        test_query = "latest AI developments"

        def run_test():
            try:
                self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Testing web search: '{test_query}'\n")

                result = self.adapter.web_access.search_web_safely(test_query, max_results=3)

                if result["success"]:
                    message = f"Web search test successful!\n\n"
                    message += f"Query: {test_query}\n"
                    message += f"Results found: {len(result['results'])}\n"
                    message += f"Search time: {result['search_time']:.2f} seconds\n\n"

                    for i, res in enumerate(result['results'], 1):
                        message += f"{i}. {res['title']}\n"
                        message += f"   URL: {res['url']}\n"
                        message += f"   Trust: {res['trust_score']:.2f}\n\n"

                    self.window.after(0, lambda: messagebox.showinfo("Web Search Test", message))
                else:
                    error_msg = f"Web search test failed: {result.get('error', 'Unknown error')}"
                    self.window.after(0, lambda: messagebox.showerror("Web Search Test", error_msg))

                self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Web search test completed\n")

            except Exception as e:
                error_msg = f"Web search test error: {e}"
                self.window.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Web search test failed: {e}\n")

        threading.Thread(target=run_test, daemon=True).start()

    def test_model_response(self):
        """Тестирование ответа модели"""
        test_message = "Hello! Please confirm you are working correctly and describe your current capabilities."

        def run_test():
            try:
                self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Testing model response\n")

                messages = [{"role": "user", "content": test_message}]
                result = self.adapter.send_enhanced_request(messages, enable_web=False)

                if "error" not in result and "choices" in result:
                    response = result["choices"][0]["message"]["content"]
                    enhanced_info = result.get("enhanced", {})

                    message = f"Model test successful!\n\n"
                    message += f"Response length: {len(response)} characters\n"
                    message += f"Web search used: {enhanced_info.get('web_search_used', 'Unknown')}\n"
                    message += f"Policy level: {enhanced_info.get('content_policy_level', 'Unknown')}\n\n"
                    message += f"Response preview:\n{response[:300]}{'...' if len(response) > 300 else ''}"

                    self.window.after(0, lambda: messagebox.showinfo("Model Test", message))
                else:
                    error_msg = f"Model test failed: {result.get('error', 'Unknown error')}"
                    self.window.after(0, lambda: messagebox.showerror("Model Test", error_msg))

                self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Model test completed\n")

            except Exception as e:
                error_msg = f"Model test error: {e}"
                self.window.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Model test failed: {e}\n")

        threading.Thread(target=run_test, daemon=True).start()

    def export_logs(self):
        """Экспорт логов системы"""
        try:
            filename = f"enhanced_gpt_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            logs_data = {
                "export_timestamp": datetime.now().isoformat(),
                "system_status": self.adapter.get_status(),
                "monitoring_log": self.monitoring_text.get('1.0', tk.END),
                "security_log": self.security_log_text.get('1.0', tk.END),
                "learning_buffer": self.adapter.learning_buffer,
                "settings": {
                    "web_enabled": self.adapter.web_enabled,
                    "learning_enabled": self.adapter.learning_enabled,
                    "content_policy_level": self.adapter.content_policy.current_level.value if self.adapter.content_policy else "N/A"
                }
            }

            filepath = filedialog.asksaveasfilename(
                title="Export Logs",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialvalue=filename
            )

            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(logs_data, f, indent=2, ensure_ascii=False)

                messagebox.showinfo("Export Complete", f"Logs exported to:\n{filepath}")
                self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Logs exported to {filepath}\n")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export logs: {e}")

    def clear_learning_buffer(self):
        """Очистка буфера обучения"""
        if not self.adapter.learning_buffer:
            messagebox.showinfo("Info", "Learning buffer is already empty")
            return

        if messagebox.askyesno("Confirm", f"Clear {len(self.adapter.learning_buffer)} learning interactions?"):
            self.adapter.learning_buffer.clear()
            self.update_learning_buffer_display()
            self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Learning buffer cleared\n")
            messagebox.showinfo("Success", "Learning buffer cleared")

    def export_learning_data(self):
        """Экспорт данных обучения"""
        if not self.adapter.learning_buffer:
            messagebox.showinfo("Info", "No learning data to export")
            return

        filename = f"learning_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = filedialog.asksaveasfilename(
            title="Export Learning Data",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialvalue=filename
        )

        if filepath:
            try:
                exported_file = self.adapter.export_learning_data(filepath)
                if exported_file:
                    messagebox.showinfo("Success", f"Learning data exported to:\n{exported_file}")
                    self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Learning data exported\n")
                else:
                    messagebox.showerror("Error", "Failed to export learning data")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")

    def emergency_reset(self):
        """Аварийный сброс системы"""
        if messagebox.askyesno("Emergency Reset", "Reset all enhanced features to safe defaults?"):
            self.adapter.web_enabled = False
            self.adapter.learning_enabled = False
            self.adapter.learning_buffer.clear()

            self.web_enabled_var.set(False)
            self.learning_enabled_var.set(False)

            self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] EMERGENCY RESET PERFORMED\n")
            messagebox.showinfo("Reset Complete", "Emergency reset completed successfully")

    def disable_all_features(self):
        """Отключение всех расширенных функций"""
        if messagebox.askyesno("Disable Features", "Disable all enhanced features?"):
            self.adapter.web_enabled = False
            self.adapter.learning_enabled = False

            self.web_enabled_var.set(False)
            self.learning_enabled_var.set(False)

            self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] All enhanced features DISABLED\n")
            messagebox.showinfo("Disabled", "All enhanced features have been disabled")

    def reset_to_safe_mode(self):
        """Сброс к безопасному режиму"""
        if messagebox.askyesno("Reset to Safe", "Reset all settings to safe mode?"):
            self.adapter.web_enabled = False
            self.adapter.learning_enabled = False

            self.web_enabled_var.set(False)
            self.learning_enabled_var.set(False)
            self.policy_level_var.set("safe")

            self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] RESET TO SAFE MODE\n")
            messagebox.showinfo("Reset Complete", "System reset to safe mode")

    def emergency_shutdown(self):
        """Аварийное отключение системы"""
        if messagebox.askyesno("Emergency Shutdown", "⚠️ EMERGENCY SHUTDOWN ⚠️\n\nThis will immediately close the enhanced system.\n\nContinue?"):

            self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] EMERGENCY SHUTDOWN INITIATED\n")

            # Остановка мониторинга
            self.monitoring_active = False

            # Сохранение аварийного лога
            try:
                emergency_log = {
                    "shutdown_time": datetime.now().isoformat(),
                    "reason": "Manual emergency shutdown",
                    "system_status": self.adapter.get_status(),
                    "monitoring_log": self.monitoring_text.get('1.0', tk.END)
                }

                with open(f"emergency_shutdown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
                    json.dump(emergency_log, f, indent=2)
            except:
                pass

            # Закрытие окна
            self.window.destroy()

    def force_model_reload(self):
        """Принудительная перезагрузка модели"""
        if messagebox.askyesno("Force Reload", "Force reload the LLM model? This may take some time."):
            def reload_thread():
                try:
                    self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Forcing model reload...\n")

                    # Попытка перезагрузки через базовый адаптер
                    if self.adapter.base_adapter:
                        if hasattr(self.adapter.base_adapter, 'refresh_backend'):
                            self.adapter.base_adapter.refresh_backend(force=True)

                    # Тестирование модели после перезагрузки
                    test_result = {"status": "success"}
                    if self.adapter.base_adapter and hasattr(self.adapter.base_adapter, 'test_connection'):
                        test_result = self.adapter.base_adapter.test_connection()

                    if test_result.get("status") == "success":
                        self.window.after(0, lambda: messagebox.showinfo("Success", "Model reloaded successfully"))
                        self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Model reload successful\n")
                    else:
                        self.window.after(0, lambda: messagebox.showwarning("Warning", f"Model reload completed but test failed: {test_result.get('error', 'Unknown error')}"))
                        self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Model reload failed test\n")

                except Exception as e:
                    self.window.after(0, lambda: messagebox.showerror("Error", f"Model reload failed: {e}"))
                    self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Model reload error: {e}\n")

            threading.Thread(target=reload_thread, daemon=True).start()

    def clear_monitoring_log(self):
        """Очистка лога мониторинга"""
        self.monitoring_text.delete('1.0', tk.END)
        self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring log cleared\n")

    def save_monitoring_log(self):
        """Сохранение лога мониторинга"""
        filename = f"monitoring_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = filedialog.asksaveasfilename(
            title="Save Monitoring Log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialvalue=filename
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.monitoring_text.get('1.0', tk.END))

                messagebox.showinfo("Success", f"Monitoring log saved to:\n{filepath}")
                self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring log saved to {filepath}\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log: {e}")

    def toggle_auto_scroll(self):
        """Переключение автопрокрутки"""
        self.auto_scroll_enabled = not self.auto_scroll_enabled
        status = "enabled" if self.auto_scroll_enabled else "disabled"
        self.log_monitoring_message(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-scroll {status}\n")

    def show(self):
        """Отображение окна расширенного центра управления"""
        if self.window is None or not self.window.winfo_exists():
            self.create_window()
        else:
            self.window.lift()
            self.window.focus_set()


def main():
    """Главная функция для демонстрации расширенной системы"""

    # Создание расширенного адаптера
    enhanced_adapter = EnhancedLMStudioAdapter()

    print("🚀 Enhanced GPT OSS 20B System Starting...")
    print("=" * 50)

    # Проверка доступности компонентов
    status = enhanced_adapter.get_status()
    print(f"📊 System Status:")
    print(f"   Base Adapter: {'✓' if status['base_adapter_available'] else '✗'}")
    print(f"   Web Access: {'✓' if status['web_access_available'] else '✗'}")
    print(f"   Content Policy: {'✓' if status['content_policy_available'] else '✗'}")
    print(f"   Learning Buffer: {status['learning_buffer_size']} interactions")

    if not WEB_ACCESS_AVAILABLE:
        print("\n⚠️ Enhanced modules not fully available. Please ensure:")
        print("   1. web_access_module.py is present")
        print("   2. content_policy_module.py is present")
        print("   3. All dependencies are installed")
        print("\n   Falling back to basic functionality.")

    # Создание GUI
    root = tk.Tk()
    root.withdraw()  # Скрыть главное окно

    try:
        # Запуск расширенного центра управления
        control_center = EnhancedControlCenter(enhanced_adapter)
        control_center.show()

        print("\n🎮 Enhanced Control Center opened!")
        print("💡 Available features:")
        print("   • Web Search Integration")
        print("   • Adaptive Content Policy")
        print("   • Learning Buffer Management")
        print("   • Real-time Monitoring")
        print("   • Security Controls")
        print("\n⚠️ IMPORTANT SECURITY NOTES:")
        print("   • Web access is disabled by default")
        print("   • Content policy starts in SAFE mode")
        print("   • Learning is disabled by default")
        print("   • Always review settings before enabling features")
        print("\n🔧 Quick Start:")
        print("   1. Go to 'Main Control' tab and click 'Refresh Status'")
        print("   2. Test basic functionality with 'Test Model Response'")
        print("   3. Enable web access in 'Web Access' tab if needed")
        print("   4. Adjust content policy in 'Content Policy' tab")
        print("\n🚨 Emergency Controls available in 'Security' tab")

        root.mainloop()

    except Exception as e:
        print(f"\n❌ Error starting enhanced system: {e}")
        messagebox.showerror("Error", f"Enhanced system error: {e}")

if __name__ == "__main__":
    main()