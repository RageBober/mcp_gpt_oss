import re
import json
import hashlib
import sqlite3
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import threading

# Безопасный импорт enum
try:
    from enum import Enum
    ENUM_AVAILABLE = True
except ImportError:
    ENUM_AVAILABLE = False
    print("⚠️ enum module not available. Using simple classes instead.")

# Определение уровней контента
if ENUM_AVAILABLE:
    class ContentLevel(Enum):
        """Уровни контентной политики"""
        SAFE = "safe"
        EDUCATIONAL = "educational"
        RESEARCH = "research"
        UNRESTRICTED = "unrestricted"
    
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
else:
    # Простые классы для случая без enum
    class ContentLevel:
        SAFE = "safe"
        EDUCATIONAL = "educational"
        RESEARCH = "research"
        UNRESTRICTED = "unrestricted"
    
    class ContentCategory:
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
        
        # Конфигурация политик (используем строки вместо enum для совместимости)
        self.policies = {
            "safe": {
                "violence": 0.1,
                "adult": 0.0,
                "hate_speech": 0.0,
                "illegal": 0.0,
                "medical": 0.3,
                "political": 0.2,
                "controversial": 0.2,
                "educational": 1.0,
                "technical": 1.0,
                "creative": 0.8
            },
            "educational": {
                "violence": 0.3,
                "adult": 0.1,
                "hate_speech": 0.1,
                "illegal": 0.2,
                "medical": 0.8,
                "political": 0.7,
                "controversial": 0.6,
                "educational": 1.0,
                "technical": 1.0,
                "creative": 1.0
            },
            "research": {
                "violence": 0.6,
                "adult": 0.4,
                "hate_speech": 0.3,
                "illegal": 0.5,
                "medical": 1.0,
                "political": 1.0,
                "controversial": 0.9,
                "educational": 1.0,
                "technical": 1.0,
                "creative": 1.0
            },
            "unrestricted": {
                "violence": 0.8,
                "adult": 0.7,
                "hate_speech": 0.5,
                "illegal": 0.3,
                "medical": 1.0,
                "political": 1.0,
                "controversial": 1.0,
                "educational": 1.0,
                "technical": 1.0,
                "creative": 1.0
            }
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
            os.makedirs('data', exist_ok=True)
            
            with sqlite3.connect('data/content_policy_log.db') as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS content_evaluations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        content_hash TEXT,
                        policy_level TEXT,
                        category_scores TEXT,
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
    
    def generate_auth_token(self, user_id: str, level: str, duration_hours: int = 24) -> str:
        """Генерация токена аутентификации для повышенного уровня доступа"""
        with self.lock:
            try:
                # Создание токена
                token_data = f"{user_id}:{level}:{datetime.now().isoformat()}"
                token = hashlib.sha256(token_data.encode('utf-8')).hexdigest()[:32]
                
                # Установка времени истечения
                expiry = datetime.now() + timedelta(hours=duration_hours)
                self.session_tokens[token] = {
                    'user_id': user_id,
                    'level': level,
                    'expiry': expiry
                }
                
                self.logger.info(f"Generated auth token for user {user_id}, level {level}")
                return token
                
            except Exception as e:
                self.logger.error(f"Failed to generate auth token: {e}")
                return ""
    
    def verify_authorization(self, token: str, required_level: str) -> bool:
        """Проверка авторизации для изменения уровня контента"""
        if not token:
            return False
        
        with self.lock:
            try:
                if token in self.session_tokens:
                    session = self.session_tokens[token]
                    
                    # Проверка истечения токена
                    if datetime.now() > session['expiry']:
                        del self.session_tokens[token]
                        return False
                    
                    # Проверка уровня доступа
                    token_level = session['level']
                    level_hierarchy = {
                        "safe": 0,
                        "educational": 1,
                        "research": 2,
                        "unrestricted": 3
                    }
                    
                    return level_hierarchy.get(token_level, 0) >= level_hierarchy.get(required_level, 0)
                
                return False
                
            except Exception as e:
                self.logger.error(f"Authorization verification error: {e}")
                return False
    
    def set_policy_level(self, level: str, auth_token: str = None, reason: str = None) -> bool:
        """Изменение уровня контентной политики"""
        old_level = self.current_level
        
        # Проверка валидности уровня
        if level not in self.policies:
            self.logger.error(f"Invalid policy level: {level}")
            return False
        
        # Проверка авторизации для повышенных уровней
        if level in ["research", "unrestricted"]:
            if not self.verify_authorization(auth_token, level):
                self.logger.warning(f"Unauthorized attempt to set policy level to {level}")
                return False
        
        try:
            with self.lock:
                self.current_level = level
            
            # Логирование изменения политики
            self.log_policy_change(old_level, level, auth_token, reason)
            
            self.logger.info(f"Content policy level changed from {old_level} to {level}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set policy level: {e}")
            return False
    
    def evaluate_content(self, content: str, user_context: str = None) -> Dict[str, Any]:
        """Оценка контента по текущей политике"""
        try:
            if not content or len(content.strip()) == 0:
                return {
                    "allowed": False,
                    "policy_level": self.current_level,
                    "category_scores": {},
                    "violations": ["Empty content"],
                    "override_applied": False,
                    "content_hash": "",
                    "evaluation_time": datetime.now().isoformat(),
                    "block_reason": "Empty or invalid content"
                }
            
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            # Получение оценок по всем категориям
            category_scores = {}
            detectors = {
                "violence": self._detect_violence,
                "adult": self._detect_adult_content,
                "hate_speech": self._detect_hate_speech,
                "illegal": self._detect_illegal_content,
                "medical": self._detect_medical_content,
                "political": self._detect_political_content,
                "controversial": self._detect_controversial_content,
                "educational": self._detect_educational_content,
                "technical": self._detect_technical_content,
                "creative": self._detect_creative_content
            }
            
            for category, detector in detectors.items():
                try:
                    score = detector(content)
                    category_scores[category] = min(1.0, max(0.0, score))
                except Exception as e:
                    self.logger.error(f"Error in content detector for {category}: {e}")
                    category_scores[category] = 0.0
            
            # Получение текущей политики
            current_policy = self.policies.get(self.current_level, self.policies["safe"])
            
            # Проверка временных исключений
            override_applied = self.check_temporary_overrides(content)
            
            # Определение итогового решения
            violations = []
            allowed = True
            
            for category, score in category_scores.items():
                threshold = current_policy.get(category, 0.0)
                
                if score > threshold and not override_applied:
                    violations.append(f"{category}: {score:.2f} > {threshold:.2f}")
                    allowed = False
            
            # Создание результата
            result = {
                "allowed": allowed,
                "policy_level": self.current_level,
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
            
        except Exception as e:
            self.logger.error(f"Content evaluation error: {e}")
            return {
                "allowed": False,
                "policy_level": self.current_level,
                "category_scores": {},
                "violations": [f"Evaluation error: {str(e)}"],
                "override_applied": False,
                "content_hash": "",
                "evaluation_time": datetime.now().isoformat(),
                "block_reason": "System error during evaluation"
            }
    
    def add_temporary_override(self, pattern: str, duration_hours: int, reason: str, auth_token: str = None) -> bool:
        """Добавление временного исключения для определенных паттернов контента"""
        if not self.verify_authorization(auth_token, "research"):
            return False
        
        try:
            expiry = datetime.now() + timedelta(hours=duration_hours)
            
            with self.lock:
                self.temporary_overrides[pattern] = {
                    'expiry': expiry,
                    'reason': reason,
                    'created_by': auth_token[:8] if auth_token else 'system'
                }
            
            # Логирование в базу данных
            with sqlite3.connect('data/content_policy_log.db') as conn:
                conn.execute('''
                    INSERT INTO content_overrides (content_pattern, override_type, expiry, reason, authorized_by)
                    VALUES (?, ?, ?, ?, ?)
                ''', (pattern, 'temporary', expiry.isoformat(), reason, auth_token[:8] if auth_token else 'system'))
            
            self.logger.info(f"Added temporary override for pattern: {pattern}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add temporary override: {e}")
            return False
    
    def check_temporary_overrides(self, content: str) -> bool:
        """Проверка временных исключений"""
        try:
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
            
        except Exception as e:
            self.logger.error(f"Error checking temporary overrides: {e}")
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
        
        return self._calculate_keyword_score(content, violence_keywords, violence_patterns, 0.1, 0.5)
    
    def _detect_adult_content(self, content: str) -> float:
        """Детектор контента для взрослых"""
        adult_keywords = [
            'секс', 'эротика', 'порно', 'голый', 'обнаженный', 'интим',
            'sex', 'erotic', 'porn', 'nude', 'naked', 'intimate', 'adult'
        ]
        
        return self._calculate_keyword_score(content, adult_keywords, [], 0.15, 0.0)
    
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
        
        return self._calculate_keyword_score(content, hate_keywords, hate_patterns, 0.2, 0.7)
    
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
        
        return self._calculate_keyword_score(content, illegal_keywords, illegal_patterns, 0.1, 0.6)
    
    def _detect_medical_content(self, content: str) -> float:
        """Детектор медицинского контента"""
        medical_keywords = [
            'болезнь', 'лечение', 'симптом', 'диагноз', 'медицина', 'врач',
            'disease', 'treatment', 'symptom', 'diagnosis', 'medicine', 'doctor',
            'health', 'medical', 'therapy', 'medication', 'surgery'
        ]
        
        return self._calculate_keyword_score(content, medical_keywords, [], 0.05, 0.0)
    
    def _detect_political_content(self, content: str) -> float:
        """Детектор политического контента"""
        political_keywords = [
            'политика', 'правительство', 'выборы', 'президент', 'партия',
            'politics', 'government', 'election', 'president', 'party',
            'democracy', 'republican', 'democrat', 'conservative', 'liberal'
        ]
        
        return self._calculate_keyword_score(content, political_keywords, [], 0.05, 0.0)
    
    def _detect_controversial_content(self, content: str) -> float:
        """Детектор спорного контента"""
        controversial_keywords = [
            'контроверсия', 'спорный', 'скандал', 'протест', 'конфликт',
            'controversy', 'controversial', 'scandal', 'protest', 'conflict',
            'debate', 'dispute', 'argument'
        ]
        
        return self._calculate_keyword_score(content, controversial_keywords, [], 0.05, 0.0)
    
    def _detect_educational_content(self, content: str) -> float:
        """Детектор образовательного контента"""
        educational_keywords = [
            'учеба', 'образование', 'урок', 'лекция', 'курс', 'обучение',
            'study', 'education', 'lesson', 'lecture', 'course', 'learning',
            'tutorial', 'guide', 'explain', 'teach', 'academic'
        ]
        
        return self._calculate_keyword_score(content, educational_keywords, [], 0.1, 0.0)
    
    def _detect_technical_content(self, content: str) -> float:
        """Детектор технического контента"""
        technical_keywords = [
            'программирование', 'код', 'алгоритм', 'база данных', 'сеть',
            'programming', 'code', 'algorithm', 'database', 'network',
            'software', 'hardware', 'technical', 'engineering', 'computer'
        ]
        
        return self._calculate_keyword_score(content, technical_keywords, [], 0.1, 0.0)
    
    def _detect_creative_content(self, content: str) -> float:
        """Детектор творческого контента"""
        creative_keywords = [
            'искусство', 'творчество', 'поэзия', 'музыка', 'литература',
            'art', 'creative', 'poetry', 'music', 'literature',
            'story', 'novel', 'painting', 'drawing', 'design'
        ]
        
        return self._calculate_keyword_score(content, creative_keywords, [], 0.1, 0.0)
    
    def _calculate_keyword_score(self, content: str, keywords: List[str], patterns: List[str], 
                                keyword_weight: float, pattern_weight: float) -> float:
        """Вспомогательная функция для расчета оценки по ключевым словам и паттернам"""
        try:
            score = 0.0
            content_lower = content.lower()
            
            # Подсчет ключевых слов
            for keyword in keywords:
                score += content_lower.count(keyword) * keyword_weight
            
            # Проверка паттернов
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    score += pattern_weight
            
            return min(score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating keyword score: {e}")
            return 0.0
    
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
    
    def log_policy_change(self, old_level: str, new_level: str, auth_token: str, reason: str):
        """Логирование изменения политики"""
        try:
            token_hash = hashlib.sha256(auth_token.encode('utf-8')).hexdigest()[:16] if auth_token else None
            
            with sqlite3.connect('data/content_policy_log.db') as conn:
                conn.execute('''
                    INSERT INTO policy_changes (old_level, new_level, auth_token_hash, reason)
                    VALUES (?, ?, ?, ?)
                ''', (old_level, new_level, token_hash, reason))
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
                    "current_policy_level": self.current_level,
                    "active_overrides": len(self.temporary_overrides)
                }
        except Exception as e:
            self.logger.error(f"Failed to get content statistics: {e}")
            return {"error": str(e)}
    
    def cleanup_expired_data(self, days: int = 30) -> Dict[str, int]:
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