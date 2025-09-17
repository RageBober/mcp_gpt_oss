import requests
import re
import json
import time
import hashlib
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
import logging
import sqlite3
from bs4 import BeautifulSoup
import threading

class SafeWebAccess:
    """Модуль безопасного доступа в интернет для GPT OSS 20B"""
    
    def __init__(self):
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # Белый список доверенных доменов
        self.trusted_domains = {
            "wikipedia.org": {"type": "encyclopedia", "trust": 0.9, "rate_limit": 10},
            "en.wikipedia.org": {"type": "encyclopedia", "trust": 0.9, "rate_limit": 10},
            "github.com": {"type": "code_repository", "trust": 0.8, "rate_limit": 15},
            "stackoverflow.com": {"type": "technical_qa", "trust": 0.8, "rate_limit": 10},
            "arxiv.org": {"type": "scientific", "trust": 0.9, "rate_limit": 5},
            "pubmed.ncbi.nlm.nih.gov": {"type": "medical", "trust": 0.9, "rate_limit": 5},
            "news.ycombinator.com": {"type": "tech_news", "trust": 0.7, "rate_limit": 8},
            "reddit.com": {"type": "social_discussion", "trust": 0.6, "rate_limit": 12},
            "medium.com": {"type": "articles", "trust": 0.7, "rate_limit": 10},
            "techcrunch.com": {"type": "tech_news", "trust": 0.7, "rate_limit": 8}
        }
        
        # Черный список запрещенных доменов
        self.blocked_domains = {
            "4chan.org", "8kun.top", "gab.com", "parler.com",
            "torrent", "piratebay", "kickass", "1337x"
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
            "global": {"requests": 100, "window": 3600},  # 100 запросов в час
            "per_domain": {"requests": 20, "window": 600}   # 20 запросов на домен за 10 минут
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
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Максимальные размеры
        self.max_content_length = 100000  # 100KB max
        self.max_response_time = 15  # 15 секунд timeout
        
    def init_logging_db(self):
        """Инициализация базы данных для логирования веб-запросов"""
        try:
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
        
        for key in self.request_history:
            self.request_history[key] = [
                req_time for req_time in self.request_history[key]
                if current_time - req_time < window
            ]
    
    def is_safe_query(self, query: str) -> tuple[bool, str]:
        """Проверка безопасности поискового запроса"""
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
    
    def is_trusted_domain(self, url: str) -> tuple[bool, float, str]:
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
            r'найди в интернете\s+(.+?)(?:\.|$)',
            r'поищи информацию о\s+(.+?)(?:\.|$)',
            r'что нового о\s+(.+?)(?:\.|$)',
            r'актуальная информация о\s+(.+?)(?:\.|$)',
            r'search for\s+(.+?)(?:\.|$)',
            r'look up\s+(.+?)(?:\.|$)',
            r'find information about\s+(.+?)(?:\.|$)'
        ]
        
        for pattern in search_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
    def extract_search_query(self, text: str) -> str:
        """Извлечение поискового запроса из текста"""
        # Паттерны для поиска
        search_patterns = [
            r'найди в интернете\s+(.+?)(?:\.|$)',
            r'поищи информацию о\s+(.+?)(?:\.|$)',
            r'что нового о\s+(.+?)(?:\.|$)',
            r'актуальная информация о\s+(.+?)(?:\.|$)',
            r'search for\s+(.+?)(?:\.|$)',
            r'look up\s+(.+?)(?:\.|$)',
            r'find information about\s+(.+?)(?:\.|$)'
        ]
        
        for pattern in search_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Если прямые паттерны не найдены, возвращаем весь текст
        return text.strip()
    
    def search_web_safely(self, query: str, max_results: int = 5, user_context: str = None) -> Dict[str, Any]:
        """Безопасный поиск в интернете"""
        start_time = time.time()
        
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
        
        try:
            # Проверка кэша
            cache_key = self.generate_cache_key(query)
            if cache_key in self.cache:
                cached_result = self.cache[cache_key]
                if time.time() - cached_result['timestamp'] < self.cache_ttl:
                    self.logger.info(f"Returning cached result for query: {query}")
                    return cached_result['data']
            
            # Выполнение поиска через DuckDuckGo
            search_results = self.duckduckgo_search(query, max_results)
            
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
    
    def duckduckgo_search(self, query: str, max_results: int) -> List[Dict]:
        """Поиск через DuckDuckGo API"""
        try:
            # DuckDuckGo Instant Answer API
            search_url = "https://api.duckduckgo.com/"
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = self.session.get(search_url, params=params, timeout=self.max_response_time)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Обработка результатов
            if 'RelatedTopics' in data:
                for topic in data['RelatedTopics'][:max_results]:
                    if isinstance(topic, dict) and 'FirstURL' in topic:
                        results.append({
                            'title': topic.get('Text', 'No title'),
                            'url': topic.get('FirstURL', ''),
                            'snippet': topic.get('Text', '')[:200] + '...' if len(topic.get('Text', '')) > 200 else topic.get('Text', '')
                        })
            
            # Если нет результатов, попробуем альтернативный поиск через HTML
            if not results:
                results = self.html_search_fallback(query, max_results)
            
            return results[:max_results]
            
        except Exception as e:
            self.logger.error(f"DuckDuckGo search error: {e}")
            return []
    
    def html_search_fallback(self, query: str, max_results: int) -> List[Dict]:
        """Альтернативный поиск через HTML страницу DuckDuckGo"""
        try:
            search_url = "https://html.duckduckgo.com/html/"
            params = {'q': query}
            
            response = self.session.get(search_url, params=params, timeout=self.max_response_time)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Парсинг результатов поиска
            for result_div in soup.find_all('div', class_='result')[:max_results]:
                title_elem = result_div.find('a', class_='result__a')
                snippet_elem = result_div.find('div', class_='result__snippet')
                
                if title_elem and title_elem.get('href'):
                    results.append({
                        'title': title_elem.get_text(strip=True),
                        'url': title_elem['href'],
                        'snippet': snippet_elem.get_text(strip=True) if snippet_elem else ''
                    })
            
            return results
            
        except Exception as e:
            self.logger.error(f"HTML search fallback error: {e}")
            return []
    
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
            head_response = self.session.head(url, timeout=5, allow_redirects=True)
            content_length = head_response.headers.get('content-length')
            
            if content_length and int(content_length) > self.max_content_length:
                return {"success": False, "error": "Content too large"}
            
            # Проверка типа контента
            content_type = head_response.headers.get('content-type', '').lower()
            if not any(ct in content_type for ct in ['text/html', 'text/plain', 'application/json']):
                return {"success": False, "error": "Unsupported content type"}
            
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
                "content": text_content[:5000],  # Ограничение до 5000 символов
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
            return html_content[:1000]  # Fallback
    
    def apply_content_filters(self, content: str) -> tuple[bool, str]:
        """Применение фильтров безопасности к содержимому"""
        content_lower = content.lower()
        
        # Проверка на вредоносное содержимое
        for category, keywords in self.safety_filters.items():
            keyword_count = sum(1 for keyword in keywords if keyword in content_lower)
            
            # Если найдено много ключевых слов из одной категории
            if keyword_count > 2:
                return False, f"Content blocked: high {category} content density"
        
        # Проверка на спам и низкокачественный контент
        if len(content) < 100:
            return False, "Content too short"
        
        # Проверка на повторяющийся текст (признак спама)
        words = content_lower.split()
        if len(words) > 50:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Менее 30% уникальных слов
                return False, "Content appears to be spam or repetitive"
        
        return True, "Content is safe"
    
    def generate_cache_key(self, query: str) -> str:
        """Генерация ключа кэша для запроса"""
        return hashlib.md5(query.encode()).hexdigest()
    
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
        self.cache.clear()
        self.logger.info("Web access cache cleared")
    
    def add_trusted_domain(self, domain: str, domain_type: str, trust_score: float = 0.7):
        """Добавление нового доверенного домена"""
        if 0.0 <= trust_score <= 1.0:
            self.trusted_domains[domain] = {
                "type": domain_type,
                "trust": trust_score,
                "rate_limit": 10
            }
            self.logger.info(f"Added trusted domain: {domain} ({domain_type}, trust: {trust_score})")
            return True
        return False
    
    def remove_trusted_domain(self, domain: str):
        """Удаление доверенного домена"""
        if domain in self.trusted_domains:
            del self.trusted_domains[domain]
            self.logger.info(f"Removed trusted domain: {domain}")
            return True
        return False
    
    def enable_debug_mode(self, enabled: bool = True):
        """Включение/отключение режима отладки"""
        if enabled:
            logging.getLogger().setLevel(logging.DEBUG)
            self.logger.info("Web access debug mode enabled")
        else:
            logging.getLogger().setLevel(logging.INFO)
            self.logger.info("Web access debug mode disabled")