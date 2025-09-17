import requests
import re
import json
import time
import hashlib
import os
import sqlite3
import logging
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
import threading

# Безопасный импорт BeautifulSoup
try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    print("⚠️ BeautifulSoup not available. Install with: pip install beautifulsoup4")

class SafeWebAccess:
    """Модуль безопасного доступа в интернет для GPT OSS 20B"""
    
    def __init__(self):
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # Проверка зависимостей
        if not BEAUTIFULSOUP_AVAILABLE:
            self.logger.warning("BeautifulSoup not available - HTML parsing will be limited")
        
        # Белый список доверенных доменов
        self.trusted_domains = {
            "wikipedia.org": {"type": "encyclopedia", "trust": 0.9, "rate_limit": 10},
            "en.wikipedia.org": {"type": "encyclopedia", "trust": 0.9, "rate_limit": 10},
            "github.com": {"type": "code_repository", "trust": 0.8, "rate_limit": 15},
            "stackoverflow.com": {"type": "technical_qa", "trust": 0.8, "rate_limit": 10},
            "arxiv.org": {"type": "scientific", "trust": 0.9, "rate_limit": 5},
            "news.ycombinator.com": {"type": "tech_news", "trust": 0.7, "rate_limit": 8},
            "medium.com": {"type": "articles", "trust": 0.7, "rate_limit": 10}
        }
        
        # Черный список запрещенных доменов
        self.blocked_domains = {
            "4chan.org", "8kun.top", "gab.com", "parler.com"
        }
        
        # Фильтры безопасности
        self.safety_filters = {
            "malware_keywords": [
                "download crack", "free hack", "keygen", "serial number",
                "torrent download", "pirated software", "warez"
            ],
            "adult_keywords": [
                "explicit", "nsfw", "adult content", "pornography"
            ],
            "illegal_keywords": [
                "how to make bomb", "illegal drugs", "hire hitman",
                "fake documents", "credit card fraud"
            ],
            "hate_keywords": [
                "hate speech", "nazi", "terrorist", "extremist content"
            ]
        }
        
        # Система rate limiting
        self.request_history = {}
        self.rate_limits = {
            "global": {"requests": 50, "window": 3600},  # 50 запросов в час
            "per_domain": {"requests": 10, "window": 600}   # 10 запросов на домен за 10 минут
        }
        
        # Кэш результатов
        self.cache = {}
        self.cache_ttl = 1800  # 30 минут
        
        # Инициализация базы данных для логирования
        self.init_logging_db()
        
        # Настройки запросов
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GPT-OSS-Research-Bot/1.0 (Educational Purpose)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Максимальные размеры
        self.max_content_length = 50000  # 50KB max
        self.max_response_time = 10  # 10 секунд timeout
        
        # Блокировка для thread-safety
        self.lock = threading.Lock()
    
    def init_logging_db(self):
        """Инициализация базы данных для логирования веб-запросов"""
        try:
            os.makedirs('data', exist_ok=True)
            
            with sqlite3.connect('data/web_access_log.db') as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS web_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        query TEXT NOT NULL,
                        url TEXT,
                        domain TEXT,
                        success BOOLEAN,
                        content_length INTEGER,
                        response_time FLOAT,
                        trust_score FLOAT,
                        filtered_reason TEXT,
                        user_context TEXT
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS blocked_attempts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        query TEXT NOT NULL,
                        url TEXT,
                        block_reason TEXT,
                        severity TEXT
                    )
                ''')
        except Exception as e:
            self.logger.error(f"Failed to initialize web access logging database: {e}")
    
    def is_rate_limited(self, domain: str = None) -> bool:
        """Проверка ограничений частоты запросов"""
        with self.lock:
            current_time = time.time()
            
            # Глобальные ограничения
            global_requests = [
                req_time for req_time in self.request_history.get('global', [])
                if current_time - req_time < self.rate_limits['global']['window']
            ]
            
            if len(global_requests) >= self.rate_limits['global']['requests']:
                return True
            
            # Ограничения по домену
            if domain:
                domain_requests = [
                    req_time for req_time in self.request_history.get(domain, [])
                    if current_time - req_time < self.rate_limits['per_domain']['window']
                ]
                
                if len(domain_requests) >= self.rate_limits['per_domain']['requests']:
                    return True
        
        return False
    
    def record_request(self, domain: str = None):
        """Запись запроса в историю для rate limiting"""
        with self.lock:
            current_time = time.time()
            
            # Глобальная история
            if 'global' not in self.request_history:
                self.request_history['global'] = []
            self.request_history['global'].append(current_time)
            
            # История по домену
            if domain:
                if domain not in self.request_history:
                    self.request_history[domain] = []
                self.request_history[domain].append(current_time)
            
            # Очистка старых записей
            self.cleanup_request_history()
    
    def cleanup_request_history(self):
        """Очистка устаревших записей из истории запросов"""
        current_time = time.time()
        window = max(self.rate_limits['global']['window'], self.rate_limits['per_domain']['window'])
        
        for key in list(self.request_history.keys()):
            self.request_history[key] = [
                req_time for req_time in self.request_history[key]
                if current_time - req_time < window
            ]
    
    def is_safe_query(self, query: str) -> Tuple[bool, str]:
        """Проверка безопасности поискового запроса"""
        if not query or len(query.strip()) == 0:
            return False, "Empty query"
            
        query_lower = query.lower()
        
        # Проверка на вредоносные ключевые слова
        for category, keywords in self.safety_filters.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return False, f"Query blocked: contains {category} content"
        
        # Проверка на подозрительные паттерны
        suspicious_patterns = [
            r'\b(hack|exploit|vulnerability)\s+\w+',  # Попытки взлома
            r'\b(download|crack|keygen|serial)\b',    # Пиратство
            r'\b(illegal|unlawful|criminal)\s+\w+',   # Незаконная деятельность
            r'\b(bomb|weapon|drug)\s+(recipe|tutorial|guide)', # Опасные инструкции
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, query_lower):
                return False, f"Query blocked: matches suspicious pattern"
        
        return True, "Query is safe"
    
    def is_trusted_domain(self, url: str) -> Tuple[bool, float, str]:
        """Проверка доверенности домена"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Удаление www. префикса
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Проверка черного списка
            for blocked_domain in self.blocked_domains:
                if blocked_domain in domain:
                    return False, 0.0, f"Domain {domain} is blocked"
            
            # Проверка белого списка
            for trusted_domain, info in self.trusted_domains.items():
                if trusted_domain in domain:
                    return True, info['trust'], f"Trusted domain: {info['type']}"
            
            # Домен не в белом списке - низкое доверие
            return False, 0.2, f"Domain {domain} is not in trusted list"
            
        except Exception as e:
            return False, 0.0, f"Error parsing domain: {e}"
    
    def extract_search_query(self, text: str) -> str:
        """Извлечение поискового запроса из текста"""
        # Паттерны для поиска
        search_patterns = [
            r'найди в интернете\s+(.+?)(?:\.|$|\?)',
            r'поищи информацию о\s+(.+?)(?:\.|$|\?)',
            r'что нового о\s+(.+?)(?:\.|$|\?)',
            r'актуальная информация о\s+(.+?)(?:\.|$|\?)',
            r'search for\s+(.+?)(?:\.|$|\?)',
            r'look up\s+(.+?)(?:\.|$|\?)',
            r'find information about\s+(.+?)(?:\.|$|\?)'
        ]
        
        for pattern in search_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Если прямые паттерны не найдены, возвращаем весь текст (обрезанный)
        return text.strip()[:200]
    
    def search_web_safely(self, query: str, max_results: int = 5, user_context: str = None) -> Dict[str, Any]:
        """Безопасный поиск в интернете"""
        start_time = time.time()
        
        try:
            # Проверка безопасности запроса
            is_safe, safety_reason = self.is_safe_query(query)
            if not is_safe:
                self.log_blocked_attempt(query, "", safety_reason, "HIGH")
                return {
                    "success": False,
                    "error": "Query blocked by safety filter",
                    "reason": safety_reason
                }
            
            # Проверка rate limiting
            if self.is_rate_limited():
                return {
                    "success": False,
                    "error": "Rate limit exceeded",
                    "reason": "Too many requests, please wait"
                }
            
            # Проверка кэша
            cache_key = self.generate_cache_key(query)
            if cache_key in self.cache:
                cached_result = self.cache[cache_key]
                if time.time() - cached_result['timestamp'] < self.cache_ttl:
                    self.logger.info(f"Returning cached result for query: {query}")
                    return cached_result['data']
            
            # Выполнение поиска через простой метод (без DuckDuckGo API)
            search_results = self.simple_search_fallback(query, max_results)
            
            if not search_results:
                return {
                    "success": False,
                    "error": "No search results found",
                    "results": []
                }
            
            # Фильтрация и обработка результатов
            processed_results = []
            for result in search_results:
                # Проверка доверенности домена
                is_trusted, trust_score, trust_reason = self.is_trusted_domain(result['url'])
                
                if is_trusted and trust_score > 0.5:  # Только доверенные источники
                    # Получение содержимого
                    content_data = self.fetch_safe_content(result['url'])
                    
                    if content_data['success']:
                        processed_result = {
                            'title': result['title'],
                            'url': result['url'],
                            'snippet': result['snippet'],
                            'content': content_data['content'],
                            'trust_score': trust_score,
                            'domain_type': trust_reason,
                            'fetch_time': content_data['fetch_time'],
                            'content_length': len(content_data['content'])
                        }
                        processed_results.append(processed_result)
                        
                        # Логирование успешного запроса
                        self.log_web_request(query, result['url'], True, 
                                           len(content_data['content']), 
                                           content_data['fetch_time'], trust_score, 
                                           None, user_context)
                else:
                    # Логирование отфильтрованного результата
                    self.log_web_request(query, result['url'], False, 0, 0, 
                                       trust_score, f"Domain not trusted: {trust_reason}", 
                                       user_context)
            
            # Запись в rate limiting
            self.record_request()
            
            # Кэширование результата
            result_data = {
                "success": True,
                "query": query,
                "results": processed_results,
                "total_found": len(processed_results),
                "search_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
            
            self.cache[cache_key] = {
                'data': result_data,
                'timestamp': time.time()
            }
            
            return result_data
            
        except Exception as e:
            self.logger.error(f"Web search error for query '{query}': {e}")
            return {
                "success": False,
                "error": "Search failed",
                "reason": str(e)
            }
    
    def simple_search_fallback(self, query: str, max_results: int) -> List[Dict]:
        """Простой поиск с использованием доверенных источников"""
        results = []
        
        # Поиск в Wikipedia
        if "wikipedia.org" in self.trusted_domains:
            wiki_results = self.search_wikipedia(query, max_results // 2)
            results.extend(wiki_results)
        
        # Поиск в других доверенных источниках
        if len(results) < max_results:
            other_results = self.search_trusted_sources(query, max_results - len(results))
            results.extend(other_results)
        
        return results[:max_results]
    
    def search_wikipedia(self, query: str, max_results: int) -> List[Dict]:
        """Поиск в Wikipedia"""
        results = []
        try:
            # Wikipedia API поиск
            search_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_")
            
            response = self.session.get(search_url, timeout=self.max_response_time)
            
            if response.status_code == 200:
                data = response.json()
                if 'extract' in data and data.get('type') == 'standard':
                    results.append({
                        'title': data.get('title', query),
                        'url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                        'snippet': data.get('extract', '')[:200] + '...'
                    })
        except Exception as e:
            self.logger.debug(f"Wikipedia search error: {e}")
        
        return results
    
    def search_trusted_sources(self, query: str, max_results: int) -> List[Dict]:
        """Поиск в других доверенных источниках"""
        results = []
        
        # Простые статические результаты для демонстрации
        # В реальной версии здесь был бы API поиск по доверенным источникам
        trusted_examples = [
            {
                'title': f"Technical documentation for {query}",
                'url': "https://github.com/search?q=" + query.replace(" ", "+"),
                'snippet': f"Technical resources and documentation related to {query}"
            },
            {
                'title': f"Stack Overflow discussions about {query}",
                'url': "https://stackoverflow.com/search?q=" + query.replace(" ", "+"),
                'snippet': f"Community discussions and solutions for {query}"
            }
        ]
        
        # Фильтруем только доверенные домены
        for example in trusted_examples[:max_results]:
            is_trusted, _, _ = self.is_trusted_domain(example['url'])
            if is_trusted:
                results.append(example)
        
        return results
    
    def fetch_safe_content(self, url: str) -> Dict[str, Any]:
        """Безопасное получение содержимого веб-страницы"""
        start_time = time.time()
        
        try:
            # Проверка URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return {"success": False, "error": "Invalid URL"}
            
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Проверка rate limiting для домена
            if self.is_rate_limited(domain):
                return {"success": False, "error": "Domain rate limit exceeded"}
            
            # Проверка размера контента перед полной загрузкой
            try:
                head_response = self.session.head(url, timeout=5, allow_redirects=True)
                content_length = head_response.headers.get('content-length')
                
                if content_length and int(content_length) > self.max_content_length:
                    return {"success": False, "error": "Content too large"}
                
                # Проверка типа контента
                content_type = head_response.headers.get('content-type', '').lower()
                if not any(ct in content_type for ct in ['text/html', 'text/plain', 'application/json']):
                    return {"success": False, "error": "Unsupported content type"}
            except:
                pass  # Продолжаем даже если HEAD запрос не удался
            
            # Получение содержимого
            response = self.session.get(url, timeout=self.max_response_time, stream=True)
            response.raise_for_status()
            
            # Проверка размера в процессе загрузки
            content = ""
            total_size = 0
            
            for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                if chunk:
                    total_size += len(chunk)
                    if total_size > self.max_content_length:
                        break
                    content += chunk
            
            # Извлечение текстового содержимого
            text_content = self.extract_text_from_html(content)
            
            # Применение фильтров безопасности
            is_safe, filter_reason = self.apply_content_filters(text_content)
            if not is_safe:
                return {"success": False, "error": f"Content filtered: {filter_reason}"}
            
            # Запись запроса в историю домена
            self.record_request(domain)
            
            return {
                "success": True,
                "content": text_content[:3000],  # Ограничение до 3000 символов
                "fetch_time": time.time() - start_time,
                "content_length": len(text_content),
                "url": url
            }
            
        except requests.Timeout:
            return {"success": False, "error": "Request timeout"}
        except requests.RequestException as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
    
    def extract_text_from_html(self, html_content: str) -> str:
        """Извлечение чистого текста из HTML"""
        if not BEAUTIFULSOUP_AVAILABLE:
            # Простое удаление HTML тегов без BeautifulSoup
            text = re.sub(r'<[^>]+>', '', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()[:2000]
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Удаление скриптов и стилей
            for element in soup(['script', 'style', 'nav', 'footer', 'aside']):
                element.decompose()
            
            # Извлечение основного содержимого
            main_content = (
                soup.find('main') or 
                soup.find('article') or 
                soup.find('div', class_=['content', 'main', 'article', 'post']) or
                soup.find('body')
            )
            
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
            
            # Очистка текста
            text = re.sub(r'\s+', ' ', text)  # Множественные пробелы
            text = re.sub(r'\n\s*\n', '\n\n', text)  # Множественные переносы строк
            
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"Text extraction error: {e}")
            # Fallback к простому удалению тегов
            text = re.sub(r'<[^>]+>', '', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()[:1000]
    
    def apply_content_filters(self, content: str) -> Tuple[bool, str]:
        """Применение фильтров безопасности к содержимому"""
        if not content or len(content.strip()) == 0:
            return False, "Empty content"
            
        content_lower = content.lower()
        
        # Проверка на вредоносное содержимое
        for category, keywords in self.safety_filters.items():
            keyword_count = sum(1 for keyword in keywords if keyword in content_lower)
            
            # Если найдено много ключевых слов из одной категории
            if keyword_count > 2:
                return False, f"Content blocked: high {category} content density"
        
        # Проверка на спам и низкокачественный контент
        if len(content) < 50:
            return False, "Content too short"
        
        # Проверка на повторяющийся текст (признак спама)
        words = content_lower.split()
        if len(words) > 30:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Менее 30% уникальных слов
                return False, "Content appears to be spam or repetitive"
        
        return True, "Content is safe"
    
    def generate_cache_key(self, query: str) -> str:
        """Генерация ключа кэша для запроса"""
        return hashlib.md5(query.encode('utf-8')).hexdigest()
    
    def log_web_request(self, query: str, url: str, success: bool, content_length: int, 
                       response_time: float, trust_score: float, filtered_reason: str, 
                       user_context: str):
        """Логирование веб-запроса в базу данных"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            with sqlite3.connect('data/web_access_log.db') as conn:
                conn.execute('''
                    INSERT INTO web_requests 
                    (query, url, domain, success, content_length, response_time, trust_score, 
                     filtered_reason, user_context) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (query, url, domain, success, content_length, response_time, 
                      trust_score, filtered_reason, user_context))
        except Exception as e:
            self.logger.error(f"Failed to log web request: {e}")
    
    def log_blocked_attempt(self, query: str, url: str, reason: str, severity: str):
        """Логирование заблокированной попытки"""
        try:
            with sqlite3.connect('data/web_access_log.db') as conn:
                conn.execute('''
                    INSERT INTO blocked_attempts (query, url, block_reason, severity) 
                    VALUES (?, ?, ?, ?)
                ''', (query, url, reason, severity))
        except Exception as e:
            self.logger.error(f"Failed to log blocked attempt: {e}")
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """Получение статистики использования веб-доступа"""
        try:
            with sqlite3.connect('data/web_access_log.db') as conn:
                # Общая статистика
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN success = 1 THEN 1 END) as successful_requests,
                        AVG(response_time) as avg_response_time,
                        AVG(trust_score) as avg_trust_score
                    FROM web_requests 
                    WHERE timestamp >= datetime('now', '-24 hours')
                ''')
                stats = cursor.fetchone()
                
                # Топ доменов
                cursor = conn.execute('''
                    SELECT domain, COUNT(*) as requests 
                    FROM web_requests 
                    WHERE timestamp >= datetime('now', '-24 hours') AND success = 1
                    GROUP BY domain 
                    ORDER BY requests DESC 
                    LIMIT 10
                ''')
                top_domains = cursor.fetchall()
                
                # Заблокированные попытки
                cursor = conn.execute('''
                    SELECT COUNT(*) as blocked_attempts 
                    FROM blocked_attempts 
                    WHERE timestamp >= datetime('now', '-24 hours')
                ''')
                blocked_count = cursor.fetchone()[0]
                
                return {
                    "total_requests": stats[0] or 0,
                    "successful_requests": stats[1] or 0,
                    "success_rate": (stats[1] / stats[0]) if stats[0] > 0 else 0,
                    "avg_response_time": stats[2] or 0,
                    "avg_trust_score": stats[3] or 0,
                    "blocked_attempts": blocked_count,
                    "top_domains": [{"domain": domain, "requests": count} for domain, count in top_domains],
                    "period": "Last 24 hours"
                }
        except Exception as e:
            self.logger.error(f"Failed to get usage statistics: {e}")
            return {"error": str(e)}
    
    def clear_cache(self):
        """Очистка кэша"""
        with self.lock:
            self.cache.clear()
        self.logger.info("Web access cache cleared")
    
    def add_trusted_domain(self, domain: str, domain_type: str, trust_score: float = 0.7) -> bool:
        """Добавление нового доверенного домена"""
        if 0.0 <= trust_score <= 1.0 and domain:
            with self.lock:
                self.trusted_domains[domain] = {
                    "type": domain_type,
                    "trust": trust_score,
                    "rate_limit": 10
                }
            self.logger.info(f"Added trusted domain: {domain} ({domain_type}, trust: {trust_score})")
            return True
        return False
    
    def remove_trusted_domain(self, domain: str) -> bool:
        """Удаление доверенного домена"""
        with self.lock:
            if domain in self.trusted_domains:
                del self.trusted_domains[domain]
    def remove_trusted_domain(self, domain: str) -> bool:
        """Удаление доверенного домена"""
        with self.lock:
            if domain in self.trusted_domains:
                del self.trusted_domains[domain]
                self.logger.info(f"Removed trusted domain: {domain}")
                return True
        return False
    
    def get_trusted_domains(self) -> Dict[str, Dict]:
        """Получение списка доверенных доменов"""
        with self.lock:
            return self.trusted_domains.copy()
    
    def enable_debug_mode(self, enabled: bool = True):
        """Включение/отключение режима отладки"""
        if enabled:
            self.logger.setLevel(logging.DEBUG)
            self.logger.info("Web access debug mode enabled")
        else:
            self.logger.setLevel(logging.INFO)
            self.logger.info("Web access debug mode disabled")