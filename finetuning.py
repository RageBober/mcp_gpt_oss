import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import json
import os
import threading
import requests
import time
from datetime import datetime
import sqlite3
from typing import List, Dict, Any
import re

class FineTuningInterface:
    """Интерфейс для быстрого дообучения GPT OSS 20B модели с поддержкой LM Studio"""
    
    def __init__(self, mcp_server=None):
        self.mcp_server = mcp_server
        self.window = None
        self.training_data = []
        self.training_in_progress = False
        
        # Адаптер для работы с LM Studio
        self.lm_studio_mode = os.getenv("LM_STUDIO_MODE", "0") == "1"
        
        # База данных для хранения примеров обучения
        self.init_training_database()
        
    def init_training_database(self):
        """Инициализация базы данных для обучающих примеров"""
        os.makedirs('data', exist_ok=True)
        self.db_path = 'data/training_examples.db'
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS training_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_text TEXT NOT NULL,
                    expected_output TEXT NOT NULL,
                    category TEXT,
                    quality_score FLOAT DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    used_count INTEGER DEFAULT 0,
                    validated BOOLEAN DEFAULT FALSE
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS fine_tuning_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    examples_count INTEGER,
                    backend_type TEXT,  -- 'ollama' или 'lm_studio'
                    model_name TEXT,
                    status TEXT DEFAULT 'created',
                    results TEXT
                )
            ''')
    
    def create_window(self):
        """Создание окна интерфейса дообучения"""
        self.window = tk.Toplevel()
        self.window.title("GPT OSS 20B - Quick Fine-tuning Interface")
        self.window.geometry("900x700")
        self.window.configure(bg='#1e1e1e')
        
        # Стиль для темной темы
        style = ttk.Style()
        style.theme_use('clam')
        
        # Настройка цветовой схемы
        style.configure('TLabel', background='#1e1e1e', foreground='#ffffff')
        style.configure('TButton', background='#3c3c3c', foreground='#ffffff')
        style.configure('TFrame', background='#1e1e1e')
        
        self.create_widgets()
        
    def create_widgets(self):
        """Создание виджетов интерфейса"""
        # Главный контейнер
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Заголовок
        backend_info = "LM Studio" if self.lm_studio_mode else "Ollama"
        title_label = ttk.Label(
            main_frame, 
            text=f"🧠 GPT OSS 20B Fine-tuning ({backend_info})",
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 10))
        
        # Notebook для вкладок
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладки
        self.create_training_tab(notebook)
        self.create_examples_tab(notebook)
        self.create_sessions_tab(notebook)
        self.create_validation_tab(notebook)
        
        # Статусная строка
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
    def create_training_tab(self, notebook):
        """Создание вкладки для обучения"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Quick Training")
        
        # Левая панель - ввод данных
        left_frame = ttk.LabelFrame(frame, text="Training Data Input")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Поле ввода
        ttk.Label(left_frame, text="Input (User message):").pack(anchor='w', padx=5, pady=(5, 0))
        self.input_text = scrolledtext.ScrolledText(left_frame, height=8, bg='#2d2d2d', fg='#ffffff')
        self.input_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Ожидаемый выход
        ttk.Label(left_frame, text="Expected Output (AI response):").pack(anchor='w', padx=5)
        self.output_text = scrolledtext.ScrolledText(left_frame, height=8, bg='#2d2d2d', fg='#ffffff')
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Категория
        category_frame = ttk.Frame(left_frame)
        category_frame.pack(fill=tk.X, padx=5)
        
        ttk.Label(category_frame, text="Category:").pack(side=tk.LEFT)
        self.category_var = tk.StringVar(value="General")
        category_combo = ttk.Combobox(
            category_frame, 
            textvariable=self.category_var,
            values=["General", "Coding", "Analysis", "Creative", "Technical", "Conversation"]
        )
        category_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Кнопки действий
        buttons_frame = ttk.Frame(left_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            buttons_frame,
            text="Add Example",
            command=self.add_training_example
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            buttons_frame,
            text="Test Current",
            command=self.test_current_example
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            buttons_frame,
            text="Clear Fields",
            command=self.clear_training_fields
        ).pack(side=tk.LEFT)
        
        # Правая панель - управление обучением
        right_frame = ttk.LabelFrame(frame, text="Training Control")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Статистика примеров
        self.stats_text = scrolledtext.ScrolledText(
            right_frame, 
            height=10, 
            width=30,
            bg='#2d2d2d', 
            fg='#ffffff'
        )
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Кнопки обучения
        training_buttons = ttk.Frame(right_frame)
        training_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            training_buttons,
            text="Start Fine-tuning",
            command=self.start_fine_tuning
        ).pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            training_buttons,
            text="Quick Validation",
            command=self.quick_validation
        ).pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            training_buttons,
            text="Load Examples",
            command=self.load_examples_from_file
        ).pack(fill=tk.X)
        
        # Обновление статистики
        self.update_training_stats()
        
    def create_examples_tab(self, notebook):
        """Создание вкладки управления примерами"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Examples Manager")
        
        # Список примеров
        examples_frame = ttk.LabelFrame(frame, text="Training Examples")
        examples_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview для отображения примеров
        columns = ("ID", "Category", "Input Preview", "Quality", "Used", "Validated")
        self.examples_tree = ttk.Treeview(examples_frame, columns=columns, show='headings')
        
        for col in columns:
            self.examples_tree.heading(col, text=col)
            
        self.examples_tree.column("ID", width=50)
        self.examples_tree.column("Category", width=100)
        self.examples_tree.column("Input Preview", width=300)
        self.examples_tree.column("Quality", width=80)
        self.examples_tree.column("Used", width=60)
        self.examples_tree.column("Validated", width=80)
        
        # Скроллбар
        scrollbar = ttk.Scrollbar(examples_frame, orient=tk.VERTICAL, command=self.examples_tree.yview)
        self.examples_tree.configure(yscrollcommand=scrollbar.set)
        
        self.examples_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Кнопки управления примерами
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            control_frame,
            text="Refresh List",
            command=self.refresh_examples_list
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            control_frame,
            text="Delete Selected",
            command=self.delete_selected_example
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            control_frame,
            text="Export Examples",
            command=self.export_examples
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            control_frame,
            text="Auto-Validate",
            command=self.auto_validate_examples
        ).pack(side=tk.LEFT)
        
        # Заполнение списка
        self.refresh_examples_list()
        
    def create_sessions_tab(self, notebook):
        """Создание вкладки сессий обучения"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Training Sessions")
        
        # Информация о сессиях
        sessions_frame = ttk.LabelFrame(frame, text="Fine-tuning Sessions History")
        sessions_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.sessions_text = scrolledtext.ScrolledText(
            sessions_frame,
            bg='#2d2d2d',
            fg='#ffffff'
        )
        self.sessions_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Кнопки управления сессиями
        session_buttons = ttk.Frame(frame)
        session_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            session_buttons,
            text="Refresh Sessions",
            command=self.refresh_sessions_list
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            session_buttons,
            text="Export Session Data",
            command=self.export_session_data
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            session_buttons,
            text="Clear Old Sessions",
            command=self.clear_old_sessions
        ).pack(side=tk.LEFT)
        
        # Загрузка истории сессий
        self.refresh_sessions_list()
        
    def create_validation_tab(self, notebook):
        """Создание вкладки валидации"""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Model Validation")
        
        # Тестовые запросы
        test_frame = ttk.LabelFrame(frame, text="Quick Model Test")
        test_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Поле тестового запроса
        ttk.Label(test_frame, text="Test Query:").pack(anchor='w', padx=5, pady=(5, 0))
        self.test_query = scrolledtext.ScrolledText(test_frame, height=4, bg='#2d2d2d', fg='#ffffff')
        self.test_query.pack(fill=tk.X, padx=5, pady=5)
        
        # Результат теста
        ttk.Label(test_frame, text="Model Response:").pack(anchor='w', padx=5)
        self.test_result = scrolledtext.ScrolledText(test_frame, height=10, bg='#2d2d2d', fg='#ffffff')
        self.test_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Кнопки тестирования
        test_buttons = ttk.Frame(frame)
        test_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            test_buttons,
            text="Send Test Query",
            command=self.send_test_query
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            test_buttons,
            text="Batch Validation",
            command=self.batch_validation
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            test_buttons,
            text="Performance Test",
            command=self.performance_test
        ).pack(side=tk.LEFT)
        
    def add_training_example(self):
        """Добавление примера для обучения"""
        input_text = self.input_text.get("1.0", tk.END).strip()
        output_text = self.output_text.get("1.0", tk.END).strip()
        category = self.category_var.get()
        
        if not input_text or not output_text:
            messagebox.showwarning("Warning", "Both input and output fields are required!")
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO training_examples (input_text, expected_output, category) VALUES (?, ?, ?)",
                    (input_text, output_text, category)
                )
            
            self.status_var.set(f"Training example added successfully! Category: {category}")
            self.clear_training_fields()
            self.update_training_stats()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add example: {e}")
    
    def test_current_example(self):
        """Тестирование текущего примера"""
        input_text = self.input_text.get("1.0", tk.END).strip()
        if not input_text:
            messagebox.showwarning("Warning", "Input field is required for testing!")
            return
            
        self.test_query.delete("1.0", tk.END)
        self.test_query.insert("1.0", input_text)
        self.send_test_query()
    
    def send_test_query(self):
        """Отправка тестового запроса к модели"""
        query = self.test_query.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("Warning", "Test query is required!")
            return
            
        def test_thread():
            try:
                self.status_var.set("Sending test query...")
                
                if self.lm_studio_mode:
                    # Использование LM Studio API
                    response = requests.post(
                        "http://localhost:1234/v1/chat/completions",
                        json={
                            "model": "gpt-oss-20b",
                            "messages": [{"role": "user", "content": query}],
                            "max_tokens": 2000,
                            "temperature": 0.7
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        answer = result["choices"][0]["message"]["content"]
                    else:
                        answer = f"LM Studio API Error: {response.status_code}\n{response.text}"
                else:
                    # Использование Ollama API
                    response = requests.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": "gpt-oss:20b",
                            "prompt": query,
                            "stream": False
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        answer = result.get("response", "No response received")
                    else:
                        answer = f"Ollama API Error: {response.status_code}\n{response.text}"
                
                # Обновление интерфейса в главном потоке
                self.window.after(0, lambda: self.test_result.delete("1.0", tk.END))
                self.window.after(0, lambda: self.test_result.insert("1.0", answer))
                self.window.after(0, lambda: self.status_var.set("Test query completed"))
                
            except requests.RequestException as e:
                error_msg = f"Connection error: {str(e)}"
                self.window.after(0, lambda: self.test_result.delete("1.0", tk.END))
                self.window.after(0, lambda: self.test_result.insert("1.0", error_msg))
                self.window.after(0, lambda: self.status_var.set("Test query failed"))
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                self.window.after(0, lambda: self.test_result.delete("1.0", tk.END))
                self.window.after(0, lambda: self.test_result.insert("1.0", error_msg))
                self.window.after(0, lambda: self.status_var.set("Test query failed"))
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def start_fine_tuning(self):
        """Запуск процесса дообучения"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM training_examples")
                examples_count = cursor.fetchone()[0]
                
            if examples_count < 5:
                messagebox.showwarning(
                    "Insufficient Data", 
                    f"Need at least 5 training examples. Currently have {examples_count}."
                )
                return
                
            # Создание новой сессии обучения
            backend_type = "lm_studio" if self.lm_studio_mode else "ollama"
            model_name = "gpt-oss-20b" if self.lm_studio_mode else "gpt-oss:20b"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "INSERT INTO fine_tuning_sessions (session_name, examples_count, backend_type, model_name, status) VALUES (?, ?, ?, ?, ?)",
                    (f"Session_{datetime.now().strftime('%Y%m%d_%H%M%S')}", examples_count, backend_type, model_name, "running")
                )
                session_id = cursor.lastrowid
                
            messagebox.showinfo(
                "Fine-tuning Started",
                f"Fine-tuning session {session_id} started with {examples_count} examples.\n"
                f"Backend: {backend_type.title()}\n"
                f"Model: {model_name}\n\n"
                "Note: This is a simplified fine-tuning interface. "
                "For production use, consider using dedicated fine-tuning tools."
            )
            
            self.status_var.set(f"Fine-tuning session {session_id} started")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to start fine-tuning: {e}")
    
    def clear_training_fields(self):
        """Очистка полей ввода"""
        self.input_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
    
    def update_training_stats(self):
        """Обновление статистики обучающих данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Общая статистика
                cursor = conn.execute("SELECT COUNT(*) FROM training_examples")
                total_examples = cursor.fetchone()[0]
                
                # По категориям
                cursor = conn.execute("SELECT category, COUNT(*) FROM training_examples GROUP BY category")
                categories = cursor.fetchall()
                
                # Валидированные примеры
                cursor = conn.execute("SELECT COUNT(*) FROM training_examples WHERE validated = TRUE")
                validated_count = cursor.fetchone()[0]
                
                # Формирование отчета
                stats_text = f"Training Statistics\n"
                stats_text += f"{'='*25}\n\n"
                stats_text += f"Total Examples: {total_examples}\n"
                stats_text += f"Validated: {validated_count}\n"
                stats_text += f"Validation Rate: {(validated_count/total_examples*100):.1f}%\n" if total_examples > 0 else "Validation Rate: 0%\n"
                stats_text += f"\nBy Category:\n"
                stats_text += f"{'-'*15}\n"
                
                for category, count in categories:
                    stats_text += f"{category}: {count}\n"
                
                if not categories:
                    stats_text += "No examples yet\n"
                
                # Обновление текстового поля
                self.stats_text.delete("1.0", tk.END)
                self.stats_text.insert("1.0", stats_text)
                
        except sqlite3.Error as e:
            self.status_var.set(f"Failed to update stats: {e}")
    
    def refresh_examples_list(self):
        """Обновление списка примеров"""
        try:
            # Очистка текущих элементов
            for item in self.examples_tree.get_children():
                self.examples_tree.delete(item)
                
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT id, category, input_text, quality_score, used_count, validated FROM training_examples ORDER BY created_at DESC"
                )
                
                for row in cursor.fetchall():
                    example_id, category, input_text, quality, used_count, validated = row
                    input_preview = input_text[:50] + "..." if len(input_text) > 50 else input_text
                    validated_str = "Yes" if validated else "No"
                    
                    self.examples_tree.insert("", "end", values=(
                        example_id, category, input_preview, f"{quality:.1f}", used_count, validated_str
                    ))
                    
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to refresh examples: {e}")
    
    def delete_selected_example(self):
        """Удаление выбранного примера"""
        selected = self.examples_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an example to delete!")
            return
            
        item = selected[0]
        example_id = self.examples_tree.item(item)["values"][0]
        
        if messagebox.askyesno("Confirm Delete", f"Delete example #{example_id}?"):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM training_examples WHERE id = ?", (example_id,))
                    
                self.refresh_examples_list()
                self.update_training_stats()
                self.status_var.set(f"Example #{example_id} deleted")
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to delete example: {e}")
    
    def load_examples_from_file(self):
        """Загрузка примеров из JSON файла"""
        file_path = filedialog.askopenfilename(
            title="Load Training Examples",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, list):
                messagebox.showerror("Format Error", "JSON file should contain a list of examples!")
                return
                
            loaded_count = 0
            with sqlite3.connect(self.db_path) as conn:
                for example in data:
                    if isinstance(example, dict) and 'input' in example and 'output' in example:
                        category = example.get('category', 'General')
                        conn.execute(
                            "INSERT INTO training_examples (input_text, expected_output, category) VALUES (?, ?, ?)",
                            (example['input'], example['output'], category)
                        )
                        loaded_count += 1
                        
            messagebox.showinfo("Success", f"Loaded {loaded_count} training examples!")
            self.refresh_examples_list()
            self.update_training_stats()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load examples: {e}")
    
    def export_examples(self):
        """Экспорт примеров в JSON файл"""
        file_path = filedialog.asksaveasfilename(
            title="Export Training Examples",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT input_text, expected_output, category, quality_score FROM training_examples"
                )
                
                examples = []
                for row in cursor.fetchall():
                    input_text, output_text, category, quality = row
                    examples.append({
                        "input": input_text,
                        "output": output_text,
                        "category": category,
                        "quality_score": quality
                    })
                    
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(examples, f, indent=2, ensure_ascii=False)
                
            messagebox.showinfo("Success", f"Exported {len(examples)} examples to {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export examples: {e}")
    
    def refresh_sessions_list(self):
        """Обновление списка сессий обучения"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM fine_tuning_sessions ORDER BY start_time DESC"
                )
                
                sessions_info = "Fine-tuning Sessions History\n"
                sessions_info += "=" * 50 + "\n\n"
                
                for row in cursor.fetchall():
                    session_id, name, start_time, end_time, examples_count, backend_type, model_name, status, results = row
                    
                    sessions_info += f"Session #{session_id}: {name}\n"
                    sessions_info += f"  Started: {start_time}\n"
                    sessions_info += f"  Backend: {backend_type}\n"
                    sessions_info += f"  Model: {model_name}\n"
                    sessions_info += f"  Examples: {examples_count}\n"
                    sessions_info += f"  Status: {status}\n"
                    if end_time:
                        sessions_info += f"  Ended: {end_time}\n"
                    if results:
                        sessions_info += f"  Results: {results[:100]}...\n"
                    sessions_info += "\n"
                
                if not cursor.rowcount:
                    sessions_info += "No fine-tuning sessions yet.\n"
                
                self.sessions_text.delete("1.0", tk.END)
                self.sessions_text.insert("1.0", sessions_info)
                
        except sqlite3.Error as e:
            self.status_var.set(f"Failed to load sessions: {e}")
    
    def export_session_data(self):
        """Экспорт данных сессий"""
        file_path = filedialog.asksaveasfilename(
            title="Export Session Data",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM fine_tuning_sessions")
                
                sessions = []
                for row in cursor.fetchall():
                    session_data = {
                        "id": row[0],
                        "name": row[1],
                        "start_time": row[2],
                        "end_time": row[3],
                        "examples_count": row[4],
                        "backend_type": row[5],
                        "model_name": row[6],
                        "status": row[7],
                        "results": row[8]
                    }
                    sessions.append(session_data)
                    
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
                
            messagebox.showinfo("Success", f"Exported {len(sessions)} sessions to {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export sessions: {e}")
    
    def clear_old_sessions(self):
        """Очистка старых сессий"""
        if messagebox.askyesno("Confirm", "Delete sessions older than 30 days?"):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "DELETE FROM fine_tuning_sessions WHERE start_time < datetime('now', '-30 days')"
                    )
                    deleted_count = cursor.rowcount
                    
                messagebox.showinfo("Success", f"Deleted {deleted_count} old sessions")
                self.refresh_sessions_list()
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to clear sessions: {e}")
    
    def quick_validation(self):
        """Быстрая валидация примеров"""
        def validation_thread():
            try:
                self.status_var.set("Running quick validation...")
                
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id, input_text, expected_output FROM training_examples WHERE validated = FALSE LIMIT 5"
                    )
                    examples = cursor.fetchall()
                
                if not examples:
                    self.window.after(0, lambda: messagebox.showinfo("Info", "No unvalidated examples found"))
                    return
                
                validated_count = 0
                for example_id, input_text, expected_output in examples:
                    try:
                        # Тестирование примера
                        if self.lm_studio_mode:
                            response = requests.post(
                                "http://localhost:1234/v1/chat/completions",
                                json={
                                    "model": "gpt-oss-20b",
                                    "messages": [{"role": "user", "content": input_text}],
                                    "max_tokens": 1000,
                                    "temperature": 0.7
                                },
                                timeout=30
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                model_response = result["choices"][0]["message"]["content"]
                            else:
                                continue
                        else:
                            response = requests.post(
                                "http://localhost:11434/api/generate",
                                json={
                                    "model": "gpt-oss:20b",
                                    "prompt": input_text,
                                    "stream": False
                                },
                                timeout=30
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                model_response = result.get("response", "")
                            else:
                                continue
                        
                        # Простая оценка качества (по длине и наличию ключевых слов)
                        quality_score = self.calculate_quality_score(expected_output, model_response)
                        
                        # Обновление в базе данных
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE training_examples SET validated = TRUE, quality_score = ? WHERE id = ?",
                                (quality_score, example_id)
                            )
                        
                        validated_count += 1
                        
                    except Exception:
                        continue
                
                self.window.after(0, lambda: self.status_var.set(f"Validated {validated_count} examples"))
                self.window.after(0, self.update_training_stats)
                self.window.after(0, self.refresh_examples_list)
                
            except Exception as e:
                self.window.after(0, lambda: self.status_var.set(f"Validation failed: {e}"))
        
        threading.Thread(target=validation_thread, daemon=True).start()
    
    def calculate_quality_score(self, expected: str, actual: str) -> float:
        """Простая оценка качества ответа"""
        if not actual or not expected:
            return 0.0
            
        # Нормализация текста
        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())
        
        # Пересечение слов
        intersection = len(expected_words & actual_words)
        union = len(expected_words | actual_words)
        
        # Коэффициент Жаккара
        jaccard = intersection / union if union > 0 else 0
        
        # Учет длины
        length_ratio = min(len(actual), len(expected)) / max(len(actual), len(expected))
        
        # Итоговая оценка
        return (jaccard * 0.7 + length_ratio * 0.3) * 5.0  # Шкала 0-5
    
    def auto_validate_examples(self):
        """Автоматическая валидация всех примеров"""
        if messagebox.askyesno("Confirm", "Auto-validate all unvalidated examples? This may take some time."):
            def auto_validation_thread():
                try:
                    self.status_var.set("Running auto-validation...")
                    
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.execute(
                            "SELECT id, input_text, expected_output FROM training_examples WHERE validated = FALSE"
                        )
                        examples = cursor.fetchall()
                    
                    if not examples:
                        self.window.after(0, lambda: messagebox.showinfo("Info", "No unvalidated examples found"))
                        return
                    
                    validated_count = 0
                    total_count = len(examples)
                    
                    for i, (example_id, input_text, expected_output) in enumerate(examples):
                        try:
                            # Обновление статуса
                            progress = f"Validating {i+1}/{total_count}..."
                            self.window.after(0, lambda p=progress: self.status_var.set(p))
                            
                            # Тестирование примера
                            if self.lm_studio_mode:
                                response = requests.post(
                                    "http://localhost:1234/v1/chat/completions",
                                    json={
                                        "model": "gpt-oss-20b",
                                        "messages": [{"role": "user", "content": input_text}],
                                        "max_tokens": 1000,
                                        "temperature": 0.7
                                    },
                                    timeout=30
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    model_response = result["choices"][0]["message"]["content"]
                                else:
                                    continue
                            else:
                                response = requests.post(
                                    "http://localhost:11434/api/generate",
                                    json={
                                        "model": "gpt-oss:20b",
                                        "prompt": input_text,
                                        "stream": False
                                    },
                                    timeout=30
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    model_response = result.get("response", "")
                                else:
                                    continue
                            
                            # Оценка качества
                            quality_score = self.calculate_quality_score(expected_output, model_response)
                            
                            # Обновление в базе данных
                            with sqlite3.connect(self.db_path) as conn:
                                conn.execute(
                                    "UPDATE training_examples SET validated = TRUE, quality_score = ? WHERE id = ?",
                                    (quality_score, example_id)
                                )
                            
                            validated_count += 1
                            
                            # Небольшая пауза между запросами
                            time.sleep(1)
                            
                        except Exception:
                            continue
                    
                    self.window.after(0, lambda: self.status_var.set(f"Auto-validation completed: {validated_count}/{total_count}"))
                    self.window.after(0, self.update_training_stats)
                    self.window.after(0, self.refresh_examples_list)
                    self.window.after(0, lambda: messagebox.showinfo("Validation Complete", f"Validated {validated_count} out of {total_count} examples"))
                    
                except Exception as e:
                    self.window.after(0, lambda: self.status_var.set(f"Auto-validation failed: {e}"))
                    self.window.after(0, lambda: messagebox.showerror("Error", f"Auto-validation failed: {e}"))
            
            threading.Thread(target=auto_validation_thread, daemon=True).start()
    
    def batch_validation(self):
        """Пакетная валидация с отчетом"""
        def batch_thread():
            try:
                self.status_var.set("Running batch validation...")
                
                # Выбор случайных примеров для тестирования
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id, input_text, expected_output, category FROM training_examples ORDER BY RANDOM() LIMIT 10"
                    )
                    examples = cursor.fetchall()
                
                if not examples:
                    self.window.after(0, lambda: messagebox.showinfo("Info", "No examples found for validation"))
                    return
                
                validation_results = []
                
                for example_id, input_text, expected_output, category in examples:
                    try:
                        # Отправка запроса к модели
                        if self.lm_studio_mode:
                            response = requests.post(
                                "http://localhost:1234/v1/chat/completions",
                                json={
                                    "model": "gpt-oss-20b",
                                    "messages": [{"role": "user", "content": input_text}],
                                    "max_tokens": 1000,
                                    "temperature": 0.7
                                },
                                timeout=60
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                model_response = result["choices"][0]["message"]["content"]
                                response_time = response.elapsed.total_seconds()
                            else:
                                model_response = f"API Error: {response.status_code}"
                                response_time = 0
                        else:
                            response = requests.post(
                                "http://localhost:11434/api/generate",
                                json={
                                    "model": "gpt-oss:20b",
                                    "prompt": input_text,
                                    "stream": False
                                },
                                timeout=60
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                model_response = result.get("response", "No response")
                                response_time = response.elapsed.total_seconds()
                            else:
                                model_response = f"API Error: {response.status_code}"
                                response_time = 0
                        
                        # Оценка качества
                        quality_score = self.calculate_quality_score(expected_output, model_response)
                        
                        validation_results.append({
                            "id": example_id,
                            "category": category,
                            "input": input_text[:100] + "..." if len(input_text) > 100 else input_text,
                            "expected": expected_output[:100] + "..." if len(expected_output) > 100 else expected_output,
                            "actual": model_response[:100] + "..." if len(model_response) > 100 else model_response,
                            "quality": quality_score,
                            "response_time": response_time
                        })
                        
                        time.sleep(0.5)  # Пауза между запросами
                        
                    except Exception as e:
                        validation_results.append({
                            "id": example_id,
                            "category": category,
                            "input": input_text[:50] + "...",
                            "expected": "N/A",
                            "actual": f"Error: {str(e)}",
                            "quality": 0.0,
                            "response_time": 0
                        })
                
                # Формирование отчета
                report = "Batch Validation Report\n"
                report += "=" * 50 + "\n\n"
                
                avg_quality = sum(r["quality"] for r in validation_results) / len(validation_results)
                avg_response_time = sum(r["response_time"] for r in validation_results) / len(validation_results)
                
                report += f"Average Quality Score: {avg_quality:.2f}/5.0\n"
                report += f"Average Response Time: {avg_response_time:.2f}s\n"
                report += f"Total Examples Tested: {len(validation_results)}\n\n"
                
                # Детали по каждому примеру
                for i, result in enumerate(validation_results, 1):
                    report += f"{i}. Example #{result['id']} ({result['category']})\n"
                    report += f"   Quality: {result['quality']:.2f}/5.0\n"
                    report += f"   Time: {result['response_time']:.2f}s\n"
                    report += f"   Input: {result['input']}\n"
                    report += f"   Expected: {result['expected']}\n"
                    report += f"   Actual: {result['actual']}\n\n"
                
                # Обновление интерфейса
                self.window.after(0, lambda: self.test_result.delete("1.0", tk.END))
                self.window.after(0, lambda: self.test_result.insert("1.0", report))
                self.window.after(0, lambda: self.status_var.set(f"Batch validation completed. Avg quality: {avg_quality:.2f}"))
                
            except Exception as e:
                error_msg = f"Batch validation failed: {str(e)}"
                self.window.after(0, lambda: self.test_result.delete("1.0", tk.END))
                self.window.after(0, lambda: self.test_result.insert("1.0", error_msg))
                self.window.after(0, lambda: self.status_var.set("Batch validation failed"))
        
        threading.Thread(target=batch_thread, daemon=True).start()
    
    def performance_test(self):
        """Тест производительности модели"""
        def perf_test_thread():
            try:
                self.status_var.set("Running performance test...")
                
                # Тестовые запросы разной сложности
                test_queries = [
                    "Hello, how are you?",
                    "Explain quantum computing in simple terms.",
                    "Write a Python function to calculate fibonacci numbers.",
                    "What are the main differences between machine learning and artificial intelligence?",
                    "Create a detailed plan for a small web application using modern technologies."
                ]
                
                results = []
                
                for i, query in enumerate(test_queries):
                    try:
                        start_time = time.time()
                        
                        if self.lm_studio_mode:
                            response = requests.post(
                                "http://localhost:1234/v1/chat/completions",
                                json={
                                    "model": "gpt-oss-20b",
                                    "messages": [{"role": "user", "content": query}],
                                    "max_tokens": 500,
                                    "temperature": 0.7
                                },
                                timeout=120
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                model_response = result["choices"][0]["message"]["content"]
                                tokens_used = result.get("usage", {}).get("total_tokens", 0)
                            else:
                                model_response = f"Error: {response.status_code}"
                                tokens_used = 0
                        else:
                            response = requests.post(
                                "http://localhost:11434/api/generate",
                                json={
                                    "model": "gpt-oss:20b",
                                    "prompt": query,
                                    "stream": False
                                },
                                timeout=120
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                model_response = result.get("response", "")
                                tokens_used = len(model_response.split())  # Приблизительная оценка
                            else:
                                model_response = f"Error: {response.status_code}"
                                tokens_used = 0
                        
                        end_time = time.time()
                        response_time = end_time - start_time
                        
                        results.append({
                            "query": query[:50] + "..." if len(query) > 50 else query,
                            "response_length": len(model_response),
                            "tokens": tokens_used,
                            "time": response_time,
                            "tokens_per_second": tokens_used / response_time if response_time > 0 else 0
                        })
                        
                        # Обновление прогресса
                        progress = f"Performance test: {i+1}/{len(test_queries)}"
                        self.window.after(0, lambda p=progress: self.status_var.set(p))
                        
                    except Exception as e:
                        results.append({
                            "query": query[:30] + "...",
                            "response_length": 0,
                            "tokens": 0,
                            "time": 0,
                            "tokens_per_second": 0,
                            "error": str(e)
                        })
                
                # Формирование отчета о производительности
                perf_report = "Performance Test Report\n"
                perf_report += "=" * 50 + "\n\n"
                
                total_time = sum(r["time"] for r in results)
                avg_tokens_per_sec = sum(r["tokens_per_second"] for r in results) / len(results)
                total_tokens = sum(r["tokens"] for r in results)
                
                perf_report += f"Total Test Time: {total_time:.2f}s\n"
                perf_report += f"Average Tokens/Second: {avg_tokens_per_sec:.2f}\n"
                perf_report += f"Total Tokens Generated: {total_tokens}\n"
                perf_report += f"Backend: {'LM Studio' if self.lm_studio_mode else 'Ollama'}\n\n"
                
                perf_report += "Individual Test Results:\n"
                perf_report += "-" * 30 + "\n"
                
                for i, result in enumerate(results, 1):
                    perf_report += f"{i}. {result['query']}\n"
                    perf_report += f"   Time: {result['time']:.2f}s\n"
                    perf_report += f"   Tokens: {result['tokens']}\n"
                    perf_report += f"   Tokens/sec: {result['tokens_per_second']:.2f}\n"
                    perf_report += f"   Response length: {result['response_length']} chars\n"
                    if "error" in result:
                        perf_report += f"   Error: {result['error']}\n"
                    perf_report += "\n"
                
                # Обновление интерфейса
                self.window.after(0, lambda: self.test_result.delete("1.0", tk.END))
                self.window.after(0, lambda: self.test_result.insert("1.0", perf_report))
                self.window.after(0, lambda: self.status_var.set(f"Performance test completed. Avg: {avg_tokens_per_sec:.1f} tokens/sec"))
                
            except Exception as e:
                error_msg = f"Performance test failed: {str(e)}"
                self.window.after(0, lambda: self.test_result.delete("1.0", tk.END))
                self.window.after(0, lambda: self.test_result.insert("1.0", error_msg))
                self.window.after(0, lambda: self.status_var.set("Performance test failed"))
        
        threading.Thread(target=perf_test_thread, daemon=True).start()
    
    def show(self):
        """Отображение окна дообучения"""
        if self.window is None or not self.window.winfo_exists():
            self.create_window()
        else:
            self.window.lift()
            self.window.focus_set()