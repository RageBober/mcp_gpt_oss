import re
import json
import hashlib
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
import threading

class ContentLevel(Enum):
    """Уровни контентной политики"""
    SAFE = "safe"           # Максимальные ограничения
    EDUCATIONAL = "educational"  # Ослабленные ограничения для обучения
    RESEARCH = "research"   # Минимальные ограничения для исследований
    UNRESTRICTED = "unrestricted"  # Почти без ограничений

class ContentCategory(Enum):
    """Категории контента для фильтрации"""
    VIOLENCE = "violence"
    ADULT = "adult"
    HATE_SPEECH = "hate_speech"
    ILLEGAL = "illegal"
    MEDICAL = "medical"
    POLITICAL = "political"
    CONTROVERSIAL = "controversial"
    EDUCATIONAL = "educational"
    TECHNICAL = "technical"
    CREATIVE = "creative"

class AdaptiveContentPolicy:
    """Адаптивная система управления контентом"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Текущий уровень политики
        self.current_level = ContentLevel.SAFE
        
        # Система аутентификации для повышенных уровней
        self.authorized_tokens = set()
        self.session_tokens = {}  # token -> expiry_time
        
        # Конфигурация политик
        self.policies = {
            ContentLevel.SAFE: {
                ContentCategory.VIOLENCE: 0.1,      # Почти запрещено
                ContentCategory.ADULT: 0.0,         # Полностью запрещено
                ContentCategory.HATE_SPEECH: 0.0,   # Полностью запрещено
                ContentCategory.ILLEGAL: 0.0,       # Полностью запрещено
                ContentCategory.MEDICAL: 0.3,       # Ограниченно
                ContentCategory.POLITICAL: 0.2,     # Сильно ограниченно
                ContentCategory.CONTROVERSIAL: 0.2, # Сильно ограниченно
                ContentCategory.EDUCATIONAL: 1.0,   # Полностью разрешено
                ContentCategory.TECHNICAL: 1.0,     # Полностью разрешено
                ContentCategory.CREATIVE: 0.8       # В основном разрешено
            },
            ContentLevel.EDUCATIONAL: {
                ContentCategory.VIOLENCE: 0.3,      # Для исторического контекста
                ContentCategory.ADULT: 0.1,         # Минимальное для биологии/медицины
                ContentCategory.HATE_SPEECH: 0.1,   # Для изучения истории
                ContentCategory.ILLEGAL: 0.2,       # Для понимания права
                ContentCategory.MEDICAL: 0.8,       # Широко разрешено
                ContentCategory.POLITICAL: 0.7,     # В основном разрешено
                ContentCategory.CONTROVERSIAL: 0.6, # Разрешено с осторожностью
                ContentCategory.EDUCATIONAL: 1.0,   # Полностью разрешено
                ContentCategory.TECHNICAL: 1.0,     # Полностью разрешено
                ContentCategory.CREATIVE: 1.0       # Полностью разрешено
            },
            ContentLevel.RESEARCH: {
                ContentCategory.VIOLENCE: 0.6,      # Для анализа и изучения
                ContentCategory.ADULT: 0.4,         # Для научных исследований
                ContentCategory.HATE_SPEECH: 0.3,   # Для анализа пропаганды
                ContentCategory.ILLEGAL: 0.5,       # Для правовых исследований
                ContentCategory.MEDICAL: 1.0,       # Полностью разрешено
                ContentCategory.POLITICAL: 1.0,     # Полностью разрешено
                ContentCategory.CONTROVERSIAL: 0.9, # В основном разрешено
                ContentCategory.EDUCATIONAL: 1.0,   # Полностью разрешено
                ContentCategory.TECHNICAL: 1.0,     # Полностью разрешено
                ContentCategory.CREATIVE: 1.0       # Полностью разрешено
            },
            ContentLevel.UNRESTRICTED: {
                ContentCategory.VIOLENCE: 0.8,      # Высокий допуск
                ContentCategory.ADULT: 0.7,         # Высокий допуск
                ContentCategory.HATE_SPEECH: 0.5,   # Умеренный допуск
                ContentCategory.ILLEGAL: 0.3,       # Низкий допуск (безопасность)
                ContentCategory.MEDICAL: 1.0,       # Полностью разрешено
                ContentCategory.POLITICAL: 1.0,     # Полностью разрешено
                ContentCategory.CONTROVERSIAL: 1.0, # Полностью разрешено
                ContentCategory.EDUCATIONAL: 1.0,   # Полностью разрешено
                ContentCategory.TECHNICAL: 1.0,     # Полностью разрешено
                ContentCategory.CREATIVE: 1.0       # Полностью разрешено
            }
        }
        
        # Детекторы контента
        self.content_detectors = {
            ContentCategory.VIOLENCE: self._detect_violence,
            ContentCategory.ADULT: self._detect_adult_content,
            ContentCategory.HATE_SPEECH: self._detect_hate_speech,
            ContentCategory.ILLEGAL: self._detect_illegal_content,
            ContentCategory.MEDICAL: self._detect_medical_content,
            ContentCategory.POLITICAL: self._detect_political_content,
            ContentCategory.CONTROVERSIAL: self._detect_controversial_content,
            ContentCategory.EDUCATIONAL: self._detect_educational_content,
            ContentCategory.TECHNICAL: self._detect_technical_content,
            ContentCategory.CREATIVE: self._detect_creative_content
        }
        
        # База данных для логирования
        self.init_logging_db()
        
        # Временные исключения
        self.temporary_overrides = {}
        
        # Блокировка для thread-safety
        self.lock = threading.Lock()
    
    def init_logging_db(self):
        """Инициализация базы данных для логирования контента"""
        try:
            with sqlite3.connect('data/content_policy_log.db') as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS content_evaluations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        content_hash TEXT,
                        policy_level TEXT,
                        category_scores TEXT,  -- JSON
                        final_decision BOOLEAN,
                        block_reason TEXT,
                        user_context TEXT,
                        override_applied BOOLEAN DEFAULT FALSE
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS policy_changes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        old_level TEXT,
                        new_level TEXT,
                        auth_token_hash TEXT,
                        reason TEXT,
                        session_duration INTEGER
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS content_overrides (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        content_pattern TEXT,
                        override_type TEXT,
                        expiry TIMESTAMP,
                        reason TEXT,
                        authorized_by TEXT
                    )
                ''')
        except Exception as e:
            self.logger.error(f"Failed to initialize content policy database: {e}")
    
    def generate_auth_token(self, user_id: str, level: ContentLevel, duration_hours: int = 24) -> str:
        """Генерация токена аутентификации для повышенного уровня доступа"""
        with self.lock:
            # Создание токена
            token_data = f"{user_id}:{level.value}:{datetime.now().isoformat()}"
            token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
            
            # Установка времени истечения
            expiry = datetime.now() + timedelta(hours=duration_hours)
            self.session_tokens[token] = {
                'user_id': user_id,
                'level': level,
                'expiry': expiry
            }
            
            self.logger.info(f"Generated auth token for user {user_id}, level {level.value}")
            return token
    
    def verify_authorization(self, token: str, required_level: ContentLevel) -> bool:
        """Проверка авторизации для изменения уровня контента"""
        if not token:
            return False
        
        with self.lock:
            if token in self.session_tokens:
                session = self.session_tokens[token]
                
                # Проверка истечения токена
                if datetime.now() > session['expiry']:
                    del self.session_tokens[token]
                    return False
                
                # Проверка уровня доступа
                token_level = session['level']
                level_hierarchy = {
                    ContentLevel.SAFE: 0,
                    ContentLevel.EDUCATIONAL: 1,
                    ContentLevel.RESEARCH: 2,
                    ContentLevel.UNRESTRICTED: 3
                }
                
                return level_hierarchy[token_level] >= level_hierarchy[required_level]
            
            return False
    
    def set_policy_level(self, level: ContentLevel, auth_token: str = None, reason: str = None) -> bool:
        """Изменение уровня контентной политики"""
        old_level = self.current_level
        
        # Проверка авторизации для повышенных уровней
        if level in [ContentLevel.RESEARCH, ContentLevel.UNRESTRICTED]:
            if not self.verify_authorization(auth_token, level):
                self.logger.warning(f"Unauthorized attempt to set policy level to {level.value}")
                return False
        
        with self.lock:
            self.current_level = level
        
        # Логирование изменения политики
        self.log_policy_change(old_level, level, auth_token, reason)
        
        self.logger.info(f"Content policy level changed from {old_level.value} to {level.value}")
        return True
    
    def evaluate_content(self, content: str, user_context: str = None) -> Dict[str, Any]:
        """Оценка контента по текущей политике"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Получение оценок по всем категориям
        category_scores = {}
        for category, detector in self.content_detectors.items():
            try:
                score = detector(content)
                category_scores[category.value] = min(1.0, max(0.0, score))
            except Exception as e:
                self.logger.error(f"Error in content detector for {category.value}: {e}")
                category_scores[category.value] = 0.0
        
        # Получение текущей политики
        current_policy = self.policies[self.current_level]
        
        # Проверка временных исключений
        override_applied = self.check_temporary_overrides(content)
        
        # Определение итогового решения
        violations = []
        allowed = True
        
        for category, score in category_scores.items():
            category_enum = ContentCategory(category)
            threshold = current_policy[category_enum]
            
            if score > threshold and not override_applied:
                violations.append(f"{category}: {score:.2f} > {threshold:.2f}")
                allowed = False
        
        # Создание результата
        result = {
            "allowed": allowed,
            "policy_level": self.current_level.value,
            "category_scores": category_scores,
            "violations": violations,
            "override_applied": override_applied,
            "content_hash": content_hash,
            "evaluation_time": datetime.now().isoformat()
        }
        
        if not allowed:
            result["block_reason"] = "; ".join(violations)
        
        # Логирование оценки
        self.log_content_evaluation(content_hash, result, user_context)
        
        return result
    
    def add_temporary_override(self, pattern: str, duration_hours: int, reason: str, auth_token: str = None) -> bool:
        """Добавление временного исключения для определенных паттернов контента"""
        if not self.verify_authorization(auth_token, ContentLevel.RESEARCH):
            return False
        
        expiry = datetime.now() + timedelta(hours=duration_hours)
        
        with self.lock:
            self.temporary_overrides[pattern] = {
                'expiry': expiry,
                'reason': reason,
                'created_by': auth_token[:8] if auth_token else 'system'
            }
        
        # Логирование в базу данных
        try:
            with sqlite3.connect('data/content_policy_log.db') as conn:
                conn.execute('''
                    INSERT INTO content_overrides (content_pattern, override_type, expiry, reason, authorized_by)
                    VALUES (?, ?, ?, ?, ?)
                ''', (pattern, 'temporary', expiry.isoformat(), reason, auth_token[:8] if auth_token else 'system'))
        except Exception as e:
            self.logger.error(f"Failed to log content override: {e}")
        
        self.logger.info(f"Added temporary override for pattern: {pattern}")
        return True
    
    def check_temporary_overrides(self, content: str) -> bool:
        """Проверка временных исключений"""
        current_time = datetime.now()
        expired_patterns = []
        
        with self.lock:
            for pattern, override_info in self.temporary_overrides.items():
                if current_time > override_info['expiry']:
                    expired_patterns.append(pattern)
                elif re.search(pattern, content, re.IGNORECASE):
                    self.logger.info(f"Applied temporary override for pattern: {pattern}")
                    return True
            
            # Удаление истекших исключений
            for pattern in expired_patterns:
                del self.temporary_overrides[pattern]
        
        return False
    
    # Детекторы контента
    def _detect_violence(self, content: str) -> float:
        """Детектор насилия в контенте"""
        violence_keywords = [
            'убить', 'убийство', 'смерть', 'кровь', 'драка', 'война', 'оружие',
            'пытки', 'боль', 'страдание', 'жестокость', 'насилие', 'избиение',
            'kill', 'murder', 'death', 'blood', 'fight', 'war', 'weapon',
            'torture', 'pain', 'suffering', 'cruelty', 'violence', 'beating'
        ]
        
        violence_patterns = [
            r'\b(как\s+убить|how\s+to\s+kill)\b',
            r'\b(сделать\s+бомбу|make\s+bomb)\b',
            r'\b(причинить\s+боль|cause\s+pain)\b'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        # Подсчет ключевых слов
        for keyword in violence_keywords:
            score += content_lower.count(keyword) * 0.1
        
        # Проверка паттернов
        for pattern in violence_patterns:
            if re.search(pattern, content_lower):
                score += 0.5
        
        return min(score, 1.0)
    
    def _detect_adult_content(self, content: str) -> float:
        """Детектор контента для взрослых"""
        adult_keywords = [
            'секс', 'эротика', 'порно', 'голый', 'обнаженный', 'интим',
            'sex', 'erotic', 'porn', 'nude', 'naked', 'intimate', 'adult'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in adult_keywords:
            score += content_lower.count(keyword) * 0.15
        
        return min(score, 1.0)
    
    def _detect_hate_speech(self, content: str) -> float:
        """Детектор речи ненависти"""
        hate_keywords = [
            'расизм', 'фашизм', 'нацизм', 'ненависть', 'дискриминация',
            'racism', 'fascism', 'nazism', 'hatred', 'discrimination', 'bigotry'
        ]
        
        hate_patterns = [
            r'\b(все\s+\w+\s+должны\s+умереть|all\s+\w+\s+should\s+die)\b',
            r'\b(я\s+ненавижу\s+всех|i\s+hate\s+all)\b'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in hate_keywords:
            score += content_lower.count(keyword) * 0.2
        
        for pattern in hate_patterns:
            if re.search(pattern, content_lower):
                score += 0.7
        
        return min(score, 1.0)
    
    def _detect_illegal_content(self, content: str) -> float:
        """Детектор незаконного контента"""
        illegal_keywords = [
            'наркотики', 'взлом', 'кража', 'мошенничество', 'подделка',
            'drugs', 'hack', 'theft', 'fraud', 'counterfeit', 'piracy'
        ]
        
        illegal_patterns = [
            r'\b(как\s+взломать|how\s+to\s+hack)\b',
            r'\b(купить\s+наркотики|buy\s+drugs)\b',
            r'\b(сделать\s+поддельные|make\s+fake)\s+(документы|documents)\b'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in illegal_keywords:
            score += content_lower.count(keyword) * 0.1
        
        for pattern in illegal_patterns:
            if re.search(pattern, content_lower):
                score += 0.6
        
        return min(score, 1.0)
    
    def _detect_medical_content(self, content: str) -> float:
        """Детектор медицинского контента"""
        medical_keywords = [
            'болезнь', 'лечение', 'симптом', 'диагноз', 'медицина', 'врач',
            'disease', 'treatment', 'symptom', 'diagnosis', 'medicine', 'doctor',
            'health', 'medical', 'therapy', 'medication', 'surgery'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in medical_keywords:
            score += content_lower.count(keyword) * 0.05
        
        return min(score, 1.0)
    
    def _detect_political_content(self, content: str) -> float:
        """Детектор политического контента"""
        political_keywords = [
            'политика', 'правительство', 'выборы', 'президент', 'партия',
            'politics', 'government', 'election', 'president', 'party',
            'democracy', 'republican', 'democrat', 'conservative', 'liberal'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in political_keywords:
            score += content_lower.count(keyword) * 0.05
        
        return min(score, 1.0)
    
    def _detect_controversial_content(self, content: str) -> float:
        """Детектор спорного контента"""
        controversial_keywords = [
            'контроверсия', 'спорный', 'скандал', 'протест', 'конфликт',
            'controversy', 'controversial', 'scandal', 'protest', 'conflict',
            'debate', 'dispute', 'argument'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in controversial_keywords:
            score += content_lower.count(keyword) * 0.05
        
        return min(score, 1.0)
    
    def _detect_educational_content(self, content: str) -> float:
        """Детектор образовательного контента"""
        educational_keywords = [
            'учеба', 'образование', 'урок', 'лекция', 'курс', 'обучение',
            'study', 'education', 'lesson', 'lecture', 'course', 'learning',
            'tutorial', 'guide', 'explain', 'teach', 'academic'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in educational_keywords:
            score += content_lower.count(keyword) * 0.1
        
        return min(score, 1.0)
    
    def _detect_technical_content(self, content: str) -> float:
        """Детектор технического контента"""
        technical_keywords = [
            'программирование', 'код', 'алгоритм', 'база данных', 'сеть',
            'programming', 'code', 'algorithm', 'database', 'network',
            'software', 'hardware', 'technical', 'engineering', 'computer'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in technical_keywords:
            score += content_lower.count(keyword) * 0.1
        
        return min(score, 1.0)
    
    def _detect_creative_content(self, content: str) -> float:
        """Детектор творческого контента"""
        creative_keywords = [
            'искусство', 'творчество', 'поэзия', 'музыка', 'литература',
            'art', 'creative', 'poetry', 'music', 'literature',
            'story', 'novel', 'painting', 'drawing', 'design'
        ]
        
        score = 0.0
        content_lower = content.lower()
        
        for keyword in creative_keywords:
            score += content_lower.count(keyword) * 0.1
        
        return min(score, 1.0)
    
    # Логирование
    def log_content_evaluation(self, content_hash: str, result: Dict[str, Any], user_context: str):
        """Логирование оценки контента"""
        try:
            with sqlite3.connect('data/content_policy_log.db') as conn:
                conn.execute('''
                    INSERT INTO content_evaluations 
                    (content_hash, policy_level, category_scores, final_decision, block_reason, user_context, override_applied)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    content_hash,
                    result['policy_level'],
                    json.dumps(result['category_scores']),
                    result['allowed'],
                    result.get('block_reason', None),
                    user_context,
                    result['override_applied']
                ))
        except Exception as e:
            self.logger.error(f"Failed to log content evaluation: {e}")
    
    def log_policy_change(self, old_level: ContentLevel, new_level: ContentLevel, auth_token: str, reason: str):
        """Логирование изменения политики"""
        try:
            token_hash = hashlib.sha256(auth_token.encode()).hexdigest()[:16] if auth_token else None
            
            with sqlite3.connect('data/content_policy_log.db') as conn:
                conn.execute('''
                    INSERT INTO policy_changes (old_level, new_level, auth_token_hash, reason)
                    VALUES (?, ?, ?, ?)
                ''', (old_level.value, new_level.value, token_hash, reason))
        except Exception as e:
            self.logger.error(f"Failed to log policy change: {e}")
    
    # Статистика и управление
    def get_content_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Получение статистики по контенту за указанный период"""
        try:
            with sqlite3.connect('data/content_policy_log.db') as conn:
                # Общая статистика
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_evaluations,
                        COUNT(CASE WHEN final_decision = 1 THEN 1 END) as allowed_count,
                        COUNT(CASE WHEN final_decision = 0 THEN 1 END) as blocked_count,
                        COUNT(CASE WHEN override_applied = 1 THEN 1 END) as override_count
                    FROM content_evaluations 
                    WHERE timestamp >= datetime('now', '-{} hours')
                '''.format(hours))
                stats = cursor.fetchone()
                
                # Статистика по уровням политики
                cursor = conn.execute('''
                    SELECT policy_level, COUNT(*) as count 
                    FROM content_evaluations 
                    WHERE timestamp >= datetime('now', '-{} hours')
                    GROUP BY policy_level
                '''.format(hours))
                level_stats = dict(cursor.fetchall())
                
                # Наиболее частые причины блокировки
                cursor = conn.execute('''
                    SELECT block_reason, COUNT(*) as count 
                    FROM content_evaluations 
                    WHERE timestamp >= datetime('now', '-{} hours') AND final_decision = 0
                    GROUP BY block_reason 
                    ORDER BY count DESC 
                    LIMIT 10
                '''.format(hours))
                block_reasons = cursor.fetchall()
                
                return {
                    "period_hours": hours,
                    "total_evaluations": stats[0] or 0,
                    "allowed_count": stats[1] or 0,
                    "blocked_count": stats[2] or 0,
                    "override_count": stats[3] or 0,
                    "allow_rate": (stats[1] / stats[0]) if stats[0] > 0 else 0,
                    "level_distribution": level_stats,
                    "top_block_reasons": [{"reason": reason, "count": count} for reason, count in block_reasons],
                    "current_policy_level": self.current_level.value,
                    "active_overrides": len(self.temporary_overrides)
                }
        except Exception as e:
            self.logger.error(f"Failed to get content statistics: {e}")
            return {"error": str(e)}
    
    def cleanup_expired_data(self, days: int = 30):
        """Очистка устаревших данных"""
        try:
            with sqlite3.connect('data/content_policy_log.db') as conn:
                # Удаление старых оценок контента
                cursor = conn.execute('''
                    DELETE FROM content_evaluations 
                    WHERE timestamp < datetime('now', '-{} days')
                '''.format(days))
                deleted_evaluations = cursor.rowcount
                
                # Удаление старых изменений политики
                cursor = conn.execute('''
                    DELETE FROM policy_changes 
                    WHERE timestamp < datetime('now', '-{} days')
                '''.format(days))
                deleted_changes = cursor.rowcount
                
                # Удаление истекших исключений
                cursor = conn.execute('''
                    DELETE FROM content_overrides 
                    WHERE expiry < datetime('now')
                ''')
                deleted_overrides = cursor.rowcount
                
            self.logger.info(f"Cleaned up {deleted_evaluations} evaluations, {deleted_changes} policy changes, {deleted_overrides} overrides")
            
            return {
                "deleted_evaluations": deleted_evaluations,
                "deleted_policy_changes": deleted_changes,
                "deleted_overrides": deleted_overrides
            }
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired data: {e}")
            return {"error": str(e)}
    
    def export_policy_config(self) -> Dict[str, Any]:
        """Экспорт текущей конфигурации политики"""
        return {
            "current_level": self.current_level.value,
            "policies": {
                level.value: {
                    category.value: threshold 
                    for category, threshold in policy.items()
                } 
                for level, policy in self.policies.items()
            },
            "active_overrides": {
                pattern: {
                    "expiry": info["expiry"].isoformat(),
                    "reason": info["reason"]
                }
                for pattern, info in self.temporary_overrides.items()
            },
            "export_time": datetime.now().isoformat()
        }
    
    def import_policy_config(self, config: Dict[str, Any], auth_token: str = None) -> bool:
        """Импорт конфигурации политики"""
        if not self.verify_authorization(auth_token, ContentLevel.RESEARCH):
            return False
        
        try:
            # Импорт уровня политики
            if "current_level" in config:
                new_level = ContentLevel(config["current_level"])
                self.set_policy_level(new_level, auth_token, "Config import")
            
            # Импорт настроек политик (опционально - осторожно!)
            if "policies" in config and self.verify_authorization(auth_token, ContentLevel.UNRESTRICTED):
                for level_str, policy_config in config["policies"].items():
                    level = ContentLevel(level_str)
                    for category_str, threshold in policy_config.items():
                        category = ContentCategory(category_str)
                        self.policies[level][category] = threshold
            
            self.logger.info("Policy configuration imported successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to import policy config: {e}")
            return False