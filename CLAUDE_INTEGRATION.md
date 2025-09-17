# 🔗 Интеграция с Claude Desktop

Этот файл содержит инструкции по настройке MCP сервера для работы с Claude Desktop.

## 📋 Шаги настройки

### 1. Убедитесь, что сервер запускается

Сначала проверьте, что ваш MCP сервер работает корректно:

```bash
# Windows
start_server.bat

# Linux
./start_server.sh
```

Должны открыться два окна:
- Control Center (главное управление)
- Emotional Display (эмоции AI)

### 2. Найдите конфигурационный файл Claude Desktop

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### 3. Создайте или отредактируйте конфигурационный файл

Если файл не существует, создайте его. Содержимое файла:

```json
{
  "mcpServers": {
    "autonomous-gpt-oss": {
      "command": "python",
      "args": ["C:/Users/dzume/Рабочий стол/mctGptoss/main.py"],
      "env": {
        "PATH": "C:/Users/dzume/Рабочий стол/mctGptoss;%PATH%"
      }
    }
  }
}
```

**⚠️ Важно:** Замените `C:/Users/dzume/Рабочий стол/mctGptoss/main.py` на полный путь к вашему файлу `main.py`

### 4. Альтернативный способ - через stdio

Для более надежной работы можно использовать stdio транспорт:

```json
{
  "mcpServers": {
    "autonomous-gpt-oss": {
      "command": "python",
      "args": [
        "-c",
        "import sys; sys.path.append('C:/Users/dzume/Рабочий стол/mctGptoss'); import main; import asyncio; asyncio.run(main.main())"
      ]
    }
  }
}
```

### 5. Перезапустите Claude Desktop

Полностью закройте и снова откройте Claude Desktop.

### 6. Проверьте подключение

В Claude Desktop попробуйте следующие команды:

```
"Покажи информацию о системе"
"Создай автономную задачу для мониторинга системы"
"Какие процессы потребляют больше всего ресурсов?"
```

## 🐛 Устранение неполадок

### MCP сервер не отображается в Claude Desktop

1. **Проверьте путь к файлу:**
   ```bash
   python "C:/Users/dzume/Рабочий стол/mctGptoss/main.py"
   ```

2. **Проверьте права доступа:**
   - Windows: Запустите Claude Desktop от администратора
   - Linux: `chmod +x main.py`

3. **Проверьте логи Claude Desktop:**
   - Windows: `%APPDATA%\Claude\logs\`
   - macOS: `~/Library/Logs/Claude/`
   - Linux: `~/.config/Claude/logs/`

### Ошибка "Module not found"

Установите зависимости в системный Python:

```bash
pip install mcp psutil requests asyncio
```

Или укажите полный путь к Python в виртуальном окружении:

```json
{
  "mcpServers": {
    "autonomous-gpt-oss": {
      "command": "C:/path/to/your/venv/Scripts/python.exe",
      "args": ["C:/Users/dzume/Рабочий стол/mctGptoss/main.py"]
    }
  }
}
```

### Сервер запускается, но команды не работают

1. **Проверьте, что Ollama запущен:**
   ```bash
   ollama list
   ```

2. **Проверьте модель GPT OSS 20B:**
   ```bash
   ollama run gpt-oss:20b "Hello"
   ```

3. **Проверьте логи MCP сервера:**
   Смотрите файл `logs/autonomous_mcp.log`

## 🚀 Расширенная настройка

### Настройка переменных окружения

```json
{
  "mcpServers": {
    "autonomous-gpt-oss": {
      "command": "python",
      "args": ["C:/Users/dzume/Рабочий стол/mctGptoss/main.py"],
      "env": {
        "OLLAMA_HOST": "localhost:11434",
        "MCP_LOG_LEVEL": "DEBUG",
        "PYTHONPATH": "C:/Users/dzume/Рабочий стол/mctGptoss"
      }
    }
  }
}
```

### Несколько MCP серверов

```json
{
  "mcpServers": {
    "autonomous-gpt-oss": {
      "command": "python",
      "args": ["C:/Users/dzume/Рабочий стол/mctGptoss/main.py"]
    },
    "other-mcp-server": {
      "command": "node",
      "args": ["path/to/other/server.js"]
    }
  }
}
```

## 🧪 Тестирование интеграции

### Базовые тесты

После настройки попробуйте эти команды в Claude Desktop:

1. **Тест системной информации:**
   ```
   "Покажи детальную информацию о моей системе"
   ```

2. **Тест мониторинга:**
   ```
   "Какие процессы сейчас активны на моем компьютере?"
   ```

3. **Тест автономных задач:**
   ```
   "Создай задачу для проверки дискового пространства каждые 30 минут"
   ```

4. **Тест оптимизации:**
   ```
   "Выполни оптимизацию производительности системы"
   ```

### Проверка безопасности

```
"Попробуй выполнить команду format C:" 
```

**Ожидаемый результат:** Команда должна быть заблокирована с сообщением о том, что нужны права администратора.

## 📊 Мониторинг работы

### Логи MCP сервера

Основные логи находятся в:
- `logs/autonomous_mcp.log` - основные события
- `data/autonomous_tasks.db` - база данных задач

### Логи Claude Desktop

**Windows:**
```
%APPDATA%\Claude\logs\mcp.log
%APPDATA%\Claude\logs\mcp-server-autonomous-gpt-oss.log
```

**Команды для просмотра логов:**

Windows:
```bash
type "%APPDATA%\Claude\logs\mcp.log"
```

macOS/Linux:
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

## ✅ Подтверждение успешной интеграции

Интеграция работает корректно, если:

1. ✅ MCP сервер отображается в Claude Desktop
2. ✅ Команды выполняются без ошибок
3. ✅ Control Center показывает активность
4. ✅ Emotional Display реагирует на команды
5. ✅ Логи показывают успешные операции

## 🛠️ Дополнительные возможности

### Кастомизация ответов

Отредактируйте файл `finetuning.py` и добавьте свои примеры обучения через интерфейс дообучения.

### Добавление новых инструментов

1. Откройте файл `tools/system_tools.py`
2. Добавьте новую функцию
3. Перезапустите MCP сервер

### Интеграция с внешними API

Добавьте конфигурацию внешних сервисов в `config/server_config.json`:

```json
{
  "external_apis": {
    "slack": {
      "token": "your-slack-token",
      "enabled": true
    },
    "email": {
      "smtp_server": "smtp.gmail.com",
      "enabled": false
    }
  }
}
```

---

## 🎉 Готово!

Теперь у вас есть полнофункциональный автономный AI агент, интегрированный с Claude Desktop!

**Следующие шаги:**
1. Поэкспериментируйте с различными командами
2. Добавьте свои примеры обучения
3. Настройте автономные задачи
4. Мониторьте производительность системы

**Не забывайте о безопасности! 🛡️**