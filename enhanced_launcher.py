#!/usr/bin/env python3
"""
🚀 Enhanced MCP Server Launcher
Запуск расширенной версии автономного MCP сервера с AI агентом
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
import logging
from pathlib import Path

# Добавляем текущую директорию в путь
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def setup_environment():
    """Настройка окружения"""
    directories = ['data', 'logs', 'checkpoints', 'config', 'backups', 'tools', 'cache']
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/enhanced_server.log'),
            logging.StreamHandler()
        ]
    )

def check_dependencies():
    """Проверка зависимостей"""
    required_modules = ['psutil', 'requests', 'sqlite3', 'tkinter']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Отсутствуют модули: {', '.join(missing_modules)}")
        print("📦 Установите их командой: pip install " + ' '.join(missing_modules))
        return False
    
    return True

def show_startup_banner():
    """Отображение стартового баннера"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        🤖 ENHANCED AUTONOMOUS MCP SERVER v2.0               ║
║                                                              ║
║  ✨ Расширенная версия с AI агентом и самообучением         ║
║                                                              ║
║  🎯 Новые возможности:                                       ║
║     • ⚙️  Управление процессами                              ║
║     • 🌐 Мониторинг сети                                    ║
║     • 💾 Автоматическое резервное копирование               ║
║     • 📊 Мониторинг производительности                      ║
║     • 📋 Планировщик задач                                  ║
║     • 🔍 Система аудита и логирования                       ║
║     • 🧠 ИИ-агент с самомодификацией                        ║
║     • 🎨 Современный графический интерфейс                  ║
║                                                              ║
║  ⚠️  ВАЖНО: Используйте с осторожностью!                    ║
║     Система имеет расширенные возможности управления        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

def main():
    """Главная функция запуска"""
    try:
        show_startup_banner()
        
        print("🔍 Проверка системы...")
        setup_environment()
        
        if not check_dependencies():
            input("Нажмите Enter для выхода...")
            return
        
        print("✅ Система готова к запуску!")
        print("🚀 Запуск Enhanced MCP Server...")
        
        # Простой GUI для демонстрации
        root = tk.Tk()
        root.title("🤖 Enhanced MCP Server v2.0")
        root.geometry("600x400")
        root.configure(bg='#1a1a1a')
        
        label = tk.Label(root, text="🤖 Enhanced MCP Server v2.0\n\n✅ Система запущена!\n\n📝 Загрузите полные модули для всех функций", 
                        bg='#1a1a1a', fg='#ffffff', font=('Arial', 14), justify='center')
        label.pack(expand=True)
        
        root.mainloop()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()