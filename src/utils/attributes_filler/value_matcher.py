# ""Match attribute values against API dictionaries.""

import logging
import re
import hashlib
import json
from typing import Dict, List, Tuple, Optional
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim
except ImportError:
    raise ImportError("Install sentence-transformers: pip install sentence-transformers")


class ValueMatcher:
    # ""Find best matching values in API dictionaries.""
    
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large"):
        # ""Initialize matcher with embedding model.""
        logging.info(f"Initializing ValueMatcher with model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        # Embeddings cache for dictionary values.
        self._embeddings_cache: Dict[str, Tuple[List[str], List[str], np.ndarray]] = {}
        logging.info("ValueMatcher initialized")
    
    def _get_dict_hash(self, values_dict: Dict[str, str]) -> str:
        # ""Create deterministic hash key for dictionary cache.""
        sorted_items = sorted(values_dict.items())
        dict_str = json.dumps(sorted_items, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(dict_str.encode('utf-8')).hexdigest()
    
    def _get_cached_embeddings(self, values_dict: Dict[str, str]) -> Tuple[List[str], List[str], np.ndarray]:
        # ""Get cached dictionary embeddings or compute them.""
        dict_hash = self._get_dict_hash(values_dict)
        
        if dict_hash in self._embeddings_cache:
            value_texts, value_codes, embeddings = self._embeddings_cache[dict_hash]
            # Ensure dictionary content still matches cache key.
            if (len(value_texts) == len(values_dict) and 
                set(value_codes) == set(values_dict.keys())):
                logging.debug(f"Using cached embeddings for dictionary ({len(values_dict)} values)")
                return value_texts, value_codes, embeddings
        
        # Compute new embeddings.
        value_texts = list(values_dict.values())
        value_codes = list(values_dict.keys())
        
        if len(value_texts) > 100:
            logging.info(f"Computing embeddings for large dictionary ({len(value_texts)} values)...")
        
        embeddings = self.model.encode(value_texts, convert_to_numpy=True, show_progress_bar=len(value_texts) > 100)
        
        self._embeddings_cache[dict_hash] = (value_texts, value_codes, embeddings)
        
        if len(value_texts) > 100:
            logging.info(f"Embeddings computed and cached for {len(value_texts)} values")
        
        return value_texts, value_codes, embeddings
    
    def find_exact_match(self, 
                        value_text: str, 
                        values_dict: Dict[str, str]) -> Optional[Tuple[str, str, float]]:
        # ""Find exact match for value in dictionary.""
        if not value_text or not values_dict:
            return None
        
        value_text_lower = value_text.lower().strip()
        
        for code, text in values_dict.items():
            if text.lower().strip() == value_text_lower:
                logging.debug(f"Exact match found: {value_text} -> {code}")
                return (code, text, 1.0)
        
        # Normalize spaces/punctuation before second exact check.
        value_normalized = re.sub(r'\s+', ' ', value_text_lower)
        for code, text in values_dict.items():
            text_normalized = re.sub(r'\s+', ' ', text.lower().strip())
            if text_normalized == value_normalized:
                logging.debug(f"Normalized exact match found: {value_text} -> {code}")
                return (code, text, 1.0)
        
        return None
    
    def find_semantic_match(self,
                           value_text: str,
                           values_dict: Dict[str, str],
                           threshold: float = 0.9) -> Optional[Tuple[str, str, float]]:
        # ""Find semantic match for a value with threshold.""
        if not value_text or not values_dict:
            return None
        
        if len(values_dict) == 0:
            return None
        
        query_embedding = self.model.encode([value_text], convert_to_numpy=True)
        
        value_texts, value_codes, value_embeddings = self._get_cached_embeddings(values_dict)
        
        similarities = cos_sim(query_embedding, value_embeddings)[0]
        
        max_idx = int(similarities.argmax())
        max_score = float(similarities[max_idx])
        
        if max_score >= threshold:
            best_code = value_codes[max_idx]
            best_text = value_texts[max_idx]
            logging.debug(f"Semantic match found: {value_text} -> {best_code} (score: {max_score:.3f})")
            return (best_code, best_text, max_score)
        
        return None
    
    def find_best_match(self,
                       value_text: str,
                       values_dict: Dict[str, str]) -> Optional[Tuple[str, str, float]]:
        """
        Ищет наиболее подходящее значение (fallback, без порога).
        
        Args:
            value_text: Текстовое значение для поиска
            values_dict: Словарь {option_code: value_text}
            
        Returns:
            Кортеж (option_code, value_text, similarity_score) или None
        """
        if not value_text or not values_dict:
            return None
        
        if len(values_dict) == 0:
            return None
        
        # Создаем эмбеддинг для искомого значения
        query_embedding = self.model.encode([value_text], convert_to_numpy=True)
        
        # Получаем эмбеддинги из кэша или создаем новые
        value_texts, value_codes, value_embeddings = self._get_cached_embeddings(values_dict)
        
        # Вычисляем косинусное сходство
        similarities = cos_sim(query_embedding, value_embeddings)[0]
        
        # Находим максимальное сходство
        max_idx = int(similarities.argmax())
        max_score = float(similarities[max_idx])
        
        best_code = value_codes[max_idx]
        best_text = value_texts[max_idx]
        
        logging.info(f"Найдено наиболее подходящее значение: {value_text} -> {best_code} (score: {max_score:.3f})")
        return (best_code, best_text, max_score)
    
    def find_multiple_matches(self,
                             value_text: str,
                             values_dict: Dict[str, str],
                             threshold: float = 0.9,
                             max_results: int = 5) -> List[Tuple[str, str, float]]:
        """
        Ищет несколько наиболее подходящих значений (для multiselect).
        
        Args:
            value_text: Текстовое значение для поиска
            values_dict: Словарь {option_code: value_text}
            threshold: Минимальный порог сходства
            max_results: Максимальное количество результатов
            
        Returns:
            Список кортежей (option_code, value_text, similarity_score)
        """
        if not value_text or not values_dict:
            return []
        
        if len(values_dict) == 0:
            return []
        
        # Создаем эмбеддинг для искомого значения
        query_embedding = self.model.encode([value_text], convert_to_numpy=True)
        
        # Получаем эмбеддинги из кэша или создаем новые
        value_texts, value_codes, value_embeddings = self._get_cached_embeddings(values_dict)
        
        # Вычисляем косинусное сходство
        similarities = cos_sim(query_embedding, value_embeddings)[0]
        
        # Получаем индексы отсортированные по убыванию сходства
        sorted_indices = similarities.argsort(descending=True)
        
        results = []
        for idx in sorted_indices[:max_results]:
            score = float(similarities[idx])
            if score >= threshold:
                code = value_codes[int(idx)]
                text = value_texts[int(idx)]
                results.append((code, text, score))
        
        return results




