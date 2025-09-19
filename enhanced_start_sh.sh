#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функция для цветного вывода
print_color() {
    echo -e "${1}${2}${NC}"
}

# Баннер
echo
print_color $CYAN "╔══════════════════════════════════════════════════════════════╗"
print_color $CYAN "║                                                              ║"
print_color $CYAN "║        🤖 ENHANCED AUTONOMOUS MCP SERVER v2.0               ║"
print_color $CYAN "║                                                              ║"
print_color $CYAN "║  ✨ Запуск расширенной версии с AI агентом                  ║"
print_color $CYAN "║                                                              ║"
print_color $CYAN "╚══════════════════════════════════════════════════════════════╝"
echo

# Определение директории скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/enhanced_launcher.py"

print_color $BLUE "[1/6] 🔍 Проверка системы..."

# Проверка Python3
if ! command -v python3 &> /dev/null; then
    print_color $RED "[ERROR] ❌ Python3 не найден!"
    print_color $YELLOW "📦 Установите Python3:"
    echo "   Ubuntu/Debian: sudo apt install python3 python3-pip python3-tk"
    echo "   CentOS/RHEL:   sudo yum install python3 python3-pip tkinter"
    echo "   Arch Linux:    sudo pacman -S python python-pip tk"
    exit 1
fi
print_color $GREEN "[✅] Python3 найден: $(python3 --version)"

# Проверка pip
if ! command -v pip3 &> /dev/null; then
    print_color $RED "[ERROR] ❌ pip3 не найден!"
    print_color $YELLOW "📦 Установите pip3:"
    echo "   Ubuntu/Debian: sudo apt install python3-pip"
    echo "   CentOS/RHEL:   sudo yum install python3-pip"
    exit 1
fi
print_color $GREEN "[✅] pip3 найден: $(pip3 --version)"

# Проверка tkinter
python3 -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    print_color $YELLOW "[WARNING] ⚠️ tkinter не найден!"
    print_color $YELLOW "📦 Установите tkinter:"
    echo "   Ubuntu/Debian: sudo apt install python3-tk"
    echo "   CentOS/RHEL:   sudo yum install tkinter"
    echo "   Arch Linux:    sudo pacman -S tk"
    echo
    read -p "Продолжить без GUI? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    print_color $GREEN "[✅] tkinter доступен"
fi

echo
print_color $BLUE "[2/6] 📦 Установка зависимостей..."

# Создание виртуального окружения (опционально)
if [ ! -d "venv" ]; then
    print_color $YELLOW "🔧 Создание виртуального окружения..."
    python3 -m venv venv
    if [ $? -eq 0 ]; then
        print_color $GREEN "[✅] Виртуальное окружение создано"
        source venv/bin/activate
        USING_VENV=true
    else
        print_color $YELLOW "[WARNING] Не удалось создать виртуальное окружение"
        USING_VENV=false
    fi
else
    print_color $BLUE "🔧 Активация виртуального окружения..."
    source venv/bin/activate
    USING_VENV=true
fi

# Установка зависимостей
print_color $YELLOW "🔧 Установка psutil..."
# Установка зависимостей
print_color $YELLOW "🔧 Установка psutil..."
pip3 install psutil --quiet --no-warn-script-location 2>/dev/null
if [ $? -eq 0 ]; then
    print_color $GREEN "[✅] psutil установлен"
else
    print_color $YELLOW "[WARNING] ⚠️ Ошибка установки psutil"
fi

print_color $YELLOW "🔧 Установка requests..."
pip3 install requests --quiet --no-warn-script-location 2>/dev/null
if [ $? -eq 0 ]; then
    print_color $GREEN "[✅] requests установлен"
else
    print_color $YELLOW "[WARNING] ⚠️ Ошибка установки requests"
fi

print_color $YELLOW "🔧 Установка beautifulsoup4..."
pip3 install beautifulsoup4 --quiet --no-warn-script-location 2>/dev/null
if [ $? -eq 0 ]; then
    print_color $GREEN "[✅] beautifulsoup4 установлен"
else
    print_color $YELLOW "[WARNING] ⚠️ Ошибка установки beautifulsoup4"
fi

print_color $GREEN "[✅] Базовые зависимости обработаны"

echo
print_color $BLUE "[3/6] 🔍 Проверка файлов..."

# Проверка наличия основных файлов
required_files=("enhanced_launcher.py" "enhanced_main_interface.py" "advanced_modules.py")

for file in "${required_files[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$file" ]; then
        print_color $RED "[ERROR] ❌ Не найден файл $file"
        print_color $YELLOW "📁 Убедитесь, что все файлы находятся в текущей директории"
        exit 1
    fi
done

print_color $GREEN "[✅] Все необходимые файлы найдены"

echo
print_color $BLUE "[4/6] 📁 Создание директорий..."

# Создание необходимых директорий
directories=("data" "logs" "config" "backups" "checkpoints" "cache")

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
done

print_color $GREEN "[✅] Структура директорий создана"

echo
print_color $BLUE "[5/6] 🛡️ Проверка безопасности..."

# Проверка прав пользователя
if [ "$EUID" -eq 0 ]; then
    print_color $YELLOW "[WARNING] ⚠️ Запуск от имени root"
    print_color $YELLOW "[WARNING] 🛡️ Будьте осторожны с системными операциями!"
    echo
    read -p "Продолжить запуск от root? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_color $RED "❌ Запуск отменен пользователем"
        exit 1
    fi
else
    print_color $GREEN "[INFO] 🔒 Запуск от имени обычного пользователя"
    print_color $BLUE "[INFO] 💡 Для расширенных возможностей может потребоваться sudo"
fi

# Проверка доступности дисплея для GUI
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    print_color $YELLOW "[WARNING] ⚠️ Графическая среда недоступна"
    print_color $BLUE "[INFO] 💻 Будет использован консольный режим"
    export GUI_DISABLED=1
fi

echo
print_color $BLUE "[6/6] 🚀 Запуск сервера..."
echo
print_color $CYAN "🎮 Запускается система управления"
print_color $CYAN "🤖 AI агент будет готов к работе"
print_color $CYAN "📊 Мониторинг системы активируется автоматически"
print_color $CYAN "⏰ Планировщик задач запустится в фоне"
echo
print_color $YELLOW "⚠️  ВАЖНО: Ознакомьтесь с предупреждениями безопасности!"
echo

# Функция обработки сигналов
cleanup() {
    print_color $YELLOW "\n🛑 Получен сигнал остановки..."
    if [ "$USING_VENV" = true ]; then
        deactivate 2>/dev/null
    fi
    print_color $BLUE "👋 До свидания!"
    exit 0
}

# Установка обработчиков сигналов
trap cleanup SIGINT SIGTERM

print_color $GREEN "Запуск через 3 секунды..."
sleep 3

# Запуск основного скрипта
cd "$SCRIPT_DIR"

if [ "$USING_VENV" = true ]; then
    python enhanced_launcher.py
else
    python3 enhanced_launcher.py
fi

# Обработка результата
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo
    print_color $RED "❌ Произошла ошибка при запуске сервера (код: $EXIT_CODE)"
    print_color $BLUE "📝 Проверьте файл logs/enhanced_server.log для деталей"
    echo
    print_color $CYAN "💡 Возможные решения:"
    echo "   • Убедитесь, что все файлы находятся в правильной директории"
    echo "   • Проверьте, что Python3 установлен корректно"
    echo "   • Установите недостающие зависимости вручную:"
    echo "     pip3 install psutil requests beautifulsoup4"
    echo "   • Для GUI проблем установите tkinter:"
    echo "     sudo apt install python3-tk  # Ubuntu/Debian"
    echo "   • Запустите с повышенными правами при необходимости"
    echo
    read -p "Нажмите Enter для выхода..."
else
    echo
    print_color $GREEN "✅ Сервер завершил работу корректно"
    print_color $BLUE "👋 До свидания!"
fi

# Деактивация виртуального окружения
if [ "$USING_VENV" = true ]; then
    deactivate 2>/dev/null
fi

exit $EXIT_CODE