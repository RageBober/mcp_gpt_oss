import os
import requests
import json
from typing import Dict, Any, List, Optional, Union
import logging
import time

class LMStudioAdapter:
    """Адаптер для работы с LM Studio API"""
    
    def __init__(self, base_url="http://localhost:1234"):
        self.base_url = base_url
        self.api_endpoint = "/v1/chat/completions"
        self.models_endpoint = "/v1/models"
        self.completions_endpoint = "/v1/completions"
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # Проверка доступности сервера при инициализации
        self.server_available = self.check_server_status()
        
    def check_server_status(self) -> bool:
        """Проверка статуса LM Studio сервера"""
        try:
            response = requests.get(f"{self.base_url}{self.models_endpoint}", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
        except Exception:
            return False
    
    def get_available_models(self) -> List[str]:
        """Получение списка доступных моделей"""
        try:
            response = requests.get(f"{self.base_url}{self.models_endpoint}", timeout=5)
            if response.status_code == 200:
                models_data = response.json()
                return [model["id"] for model in models_data.get("data", [])]
            return []
        except Exception as e:
            self.logger.error(f"Failed to get available models: {e}")
            return []
    
    def send_chat_request(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """Отправка запроса к LM Studio в формате ChatML"""
        # Настройки по умолчанию для GPT OSS 20B
        default_params = {
            "model": "gpt-oss-20b",
            "max_tokens": 4000,
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "stream": False
        }
        
        # Обновление параметров
        params = {**default_params, **kwargs}
        
        payload = {
            "model": params["model"],
            "messages": messages,
            "max_tokens": params["max_tokens"],
            "temperature": params["temperature"],
            "top_p": params["top_p"],
            "frequency_penalty": params["frequency_penalty"],
            "presence_penalty": params["presence_penalty"],
            "stream": params["stream"]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}{self.api_endpoint}",
                json=payload,
                timeout=kwargs.get("timeout", 120),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", {}).get("message", error_detail)
                except:
                    pass
                
                return {
                    "error": f"LM Studio API error: {response.status_code}",
                    "details": error_detail,
                    "status_code": response.status_code
                }
        except requests.Timeout:
            return {
                "error": "Request timeout",
                "details": "LM Studio took too long to respond"
            }
        except requests.ConnectionError:
            return {
                "error": "Connection error",
                "details": "Cannot connect to LM Studio. Make sure it's running on localhost:1234"
            }
        except Exception as e:
            return {
                "error": f"Unexpected error: {str(e)}",
                "details": f"Exception type: {type(e).__name__}"
            }
    
    def test_model_response(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Тестирование ответа модели"""
        if not model_name:
            available_models = self.get_available_models()
            if not available_models:
                return {
                    "error": "No models available",
                    "details": "Please load a model in LM Studio"
                }
            model_name = available_models[0]
        
        test_messages = [
            {
                "role": "system", 
                "content": "You are a helpful AI assistant. Please respond concisely."
            },
            {
                "role": "user", 
                "content": "Hello! Can you confirm you're working correctly? Please respond with a brief confirmation."
            }
        ]
        
        start_time = time.time()
        result = self.send_chat_request(test_messages, model=model_name, max_tokens=100)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        if "error" not in result:
            try:
                response_text = result["choices"][0]["message"]["content"]
                token_usage = result.get("usage", {})
                
                return {
                    "status": "success",
                    "model": model_name,
                    "response": response_text,
                    "response_time": round(response_time, 2),
                    "token_usage": token_usage,
                    "backend": "lm_studio"
                }
            except (KeyError, IndexError) as e:
                return {
                    "status": "error",
                    "error": "Invalid response format",
                    "details": f"Failed to parse response: {e}",
                    "raw_response": result
                }
        else:
            return {
                "status": "error",
                "model": model_name,
                "response_time": round(response_time, 2),
                "backend": "lm_studio",
                **result
            }
    
    def get_server_info(self) -> Dict[str, Any]:
        """Получение информации о сервере LM Studio"""
        try:
            # Попытка получить информацию о моделях
            models_response = requests.get(f"{self.base_url}{self.models_endpoint}", timeout=5)
            
            if models_response.status_code == 200:
                models_data = models_response.json()
                models = models_data.get("data", [])
                
                return {
                    "server_status": "running",
                    "url": self.base_url,
                    "models_loaded": len(models),
                    "available_models": [model["id"] for model in models],
                    "api_version": "v1",
                    "backend_type": "lm_studio"
                }
            else:
                return {
                    "server_status": "error",
                    "url": self.base_url,
                    "error": f"HTTP {models_response.status_code}",
                    "backend_type": "lm_studio"
                }
                
        except requests.ConnectionError:
            return {
                "server_status": "offline",
                "url": self.base_url,
                "error": "Connection refused",
                "backend_type": "lm_studio",
                "suggestion": "Make sure LM Studio is running and local server is started"
            }
        except Exception as e:
            return {
                "server_status": "unknown",
                "url": self.base_url,
                "error": str(e),
                "backend_type": "lm_studio"
            }


# Глобальные функции для упрощения использования
def get_llm_backend():
    """Определение доступного бэкенда LLM"""
    # Проверка переменной окружения
    if os.getenv("LM_STUDIO_MODE", "0") == "1":
        adapter = LMStudioAdapter()
        if adapter.check_server_status():
            return "lm_studio", adapter
        else:
            print("⚠️ LM Studio mode enabled but server not available, trying Ollama...")
    
    # Проверка Ollama
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.status_code == 200:
            return "ollama", None
    except:
        pass
    
    # Возврат к LM Studio, если ничего не найдено
    return "lm_studio", LMStudioAdapter()


class LLMManager:
    """Менеджер для работы с различными LLM бэкендами"""
    
    def __init__(self):
        self.backend_type = None
        self.adapter = None
        self.last_check = 0
        self.check_interval = 30  # Проверка доступности каждые 30 секунд
        
        self.refresh_backend()
    
    def refresh_backend(self, force: bool = False):
        """Обновление информации о доступном бэкенде"""
        current_time = time.time()
        
        if not force and (current_time - self.last_check) < self.check_interval:
            return
        
        self.backend_type, self.adapter = get_llm_backend()
        self.last_check = current_time
    
    def send_request(self, prompt: Union[str, List[Dict]], **kwargs) -> Dict[str, Any]:
        """Отправка запроса с автоматическим выбором бэкенда"""
        self.refresh_backend()
        
        if self.backend_type == "lm_studio" and self.adapter:
            if isinstance(prompt, str):
                messages = [{"role": "user", "content": prompt}]
            else:
                messages = prompt
            
            return self.adapter.send_chat_request(messages, **kwargs)
        
        elif self.backend_type == "ollama":
            # Преобразование сообщений в простой промпт для Ollama
            if isinstance(prompt, list):
                prompt_text = ""
                for msg in prompt:
                    if msg["role"] == "system":
                        prompt_text += f"System: {msg['content']}\n"
                    elif msg["role"] == "user":
                        prompt_text += f"User: {msg['content']}\n"
                    elif msg["role"] == "assistant":
                        prompt_text += f"Assistant: {msg['content']}\n"
                prompt_text += "Assistant: "
            else:
                prompt_text = prompt
            
            try:
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "gpt-oss:20b",
                        "prompt": prompt_text,
                        "stream": False
                    },
                    timeout=kwargs.get("timeout", 120)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "choices": [{
                            "message": {
                                "role": "assistant",
                                "content": result.get("response", "")
                            }
                        }],
                        "usage": {
                            "total_tokens": len(result.get("response", "").split())
                        },
                        "model": "gpt-oss:20b",
                        "backend": "ollama"
                    }
                else:
                    return {
                        "error": f"Ollama API error: {response.status_code}",
                        "details": response.text
                    }
            except Exception as e:
                return {
                    "error": f"Ollama connection error: {str(e)}"
                }
        
        else:
            return {
                "error": "No LLM backend available",
                "details": "Please start LM Studio or Ollama"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса текущего бэкенда"""
        self.refresh_backend(force=True)
        
        if self.backend_type == "lm_studio" and self.adapter:
            status_info = self.adapter.get_server_info()
        elif self.backend_type == "ollama":
            try:
                response = requests.get("http://localhost:11434/api/tags", timeout=5)
                if response.status_code == 200:
                    tags_data = response.json()
                    models = [model["name"] for model in tags_data.get("models", [])]
                    
                    status_info = {
                        "server_status": "running",
                        "url": "http://localhost:11434",
                        "models_loaded": len(models),
                        "available_models": models,
                        "backend_type": "ollama"
                    }
                else:
                    status_info = {
                        "server_status": "error",
                        "url": "http://localhost:11434",
                        "error": f"HTTP {response.status_code}",
                        "backend_type": "ollama"
                    }
            except Exception as e:
                status_info = {
                    "server_status": "offline",
                    "url": "http://localhost:11434",
                    "error": str(e),
                    "backend_type": "ollama"
                }
        else:
            status_info = {
                "server_status": "no_backend",
                "error": "No LLM backend found",
                "details": "Please start LM Studio or Ollama"
            }
        
        status_info["active_backend"] = self.backend_type
        return status_info
    
    def test_connection(self) -> Dict[str, Any]:
        """Тестирование подключения"""
        self.refresh_backend(force=True)
        
        if self.backend_type == "lm_studio" and self.adapter:
            return self.adapter.test_model_response()
        elif self.backend_type == "ollama":
            try:
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "gpt-oss:20b",
                        "prompt": "Hello, test connection",
                        "stream": False
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "status": "success",
                        "backend": "ollama",
                        "model": "gpt-oss:20b",
                        "response": result.get("response", "")
                    }
                else:
                    return {
                        "status": "error",
                        "backend": "ollama",
                        "error": f"HTTP {response.status_code}",
                        "details": response.text
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "backend": "ollama",
                    "error": str(e)
                }
        else:
            return {
                "status": "error",
                "error": "No backend available",
                "details": "Neither LM Studio nor Ollama is accessible"
            }


# Глобальный экземпляр менеджера
llm_manager = LLMManager()

# Дополнительные функции для обратной совместимости
def send_llm_request(prompt: str, **kwargs) -> Dict[str, Any]:
    """Универсальная функция для отправки запросов к LLM"""
    return llm_manager.send_request(prompt, **kwargs)

def test_llm_connection() -> Dict[str, Any]:
    """Тестирование подключения к LLM"""
    return llm_manager.test_connection()

def get_backend_info() -> Dict[str, Any]:
    """Получение информации о текущем бэкенде"""
    return llm_manager.get_status()

# Экспорт основных функций
__all__ = [
    'LMStudioAdapter',
    'LLMManager', 
    'llm_manager',
    'get_llm_backend',
    'send_llm_request',
    'test_llm_connection',
    'get_backend_info'
]