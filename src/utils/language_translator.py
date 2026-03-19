# ""Language detection and DeepL translation utilities.""

import os
import time
from typing import Optional, Tuple
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
import deepl

from .translation_cache import TranslationCache


# Make language detection deterministic.
DetectorFactory.seed = 0


class LanguageTranslator:
    # ""Detect and translate text.""
    
    def __init__(self, deepl_api_key: Optional[str] = None, cache_dir: str = "data/other"):
        # ""Initialize translator and cache.""
        self.cache = TranslationCache(cache_dir)
        
        self.api_key = deepl_api_key or os.getenv('DEEPL_API_KEY')
        
        self.translator = None
        if self.api_key:
            try:
                self.translator = deepl.Translator(self.api_key)
            except Exception as e:
                print(f"DeepL initialization failed: {e}")
        
        # Request pacing for API rate limiting.
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms между запросами
    
    def detect_language(self, text: str) -> Optional[str]:
        # ""Detect language code for text.""
        if not text or len(text.strip()) < 3:
            return None
        
        try:
            clean_text = text.strip()
            
            detected_lang = detect(clean_text)
            
            if detected_lang in ['ru', 'uk', 'en', 'de', 'fr', 'es', 'it', 'pl']:
                return detected_lang
            
            return None
            
        except LangDetectException:
            return None
    
    def is_russian_text(self, text: str) -> bool:
        # ""Return True if detected language is Russian.""
        detected_lang = self.detect_language(text)
        return detected_lang == 'ru'
    
    def _rate_limit(self) -> None:
        # ""Apply rate limiting before API request.""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        
        self.last_request_time = time.time()
    
    def translate_text(self, text: str, source_lang: str = 'ru', 
                      target_lang: str = 'uk') -> Optional[str]:
        # ""Translate text with DeepL and cache the result.""
        if not text or not text.strip():
            return text
        
        clean_text = text.strip()
        
        cached_translation = self.cache.get_general_translation(clean_text)
        if cached_translation:
            return cached_translation
        
        if not self.translator:
            print("DeepL API key is not configured. Returning original text.")
            return clean_text
        
        try:
            self._rate_limit()
            
            result = self.translator.translate_text(
                clean_text,
                source_lang=source_lang.upper(),
                target_lang=target_lang.upper()
            )
            
            translated_text = result.text
            
            self.cache.save_general_translation(
                clean_text, translated_text, source_lang, target_lang
            )
            
            return translated_text
            
        except Exception as e:
            print(f"Translation failed for '{clean_text}': {e}")
            return clean_text
    
    def translate_category(self, category_name: str) -> str:
        # ""Translate category name if it is in Russian.""
        if not category_name:
            return category_name
        
        cached_translation = self.cache.get_category_translation(category_name)
        if cached_translation:
            return cached_translation
        
        if self.is_russian_text(category_name):
            translated = self.translate_text(category_name, 'ru', 'uk')
            if translated and translated != category_name:
                self.cache.save_category_translation(category_name, translated)
                return translated
        
        return category_name
    
    def translate_param_name(self, param_name: str) -> str:
        # ""Translate parameter name if it is in Russian.""
        if not param_name:
            return param_name
        
        cached_translation = self.cache.get_param_translation(param_name)
        if cached_translation:
            return cached_translation
        
        if self.is_russian_text(param_name):
            translated = self.translate_text(param_name, 'ru', 'uk')
            if translated and translated != param_name:
                self.cache.save_param_translation(param_name, translated)
                return translated
        
        return param_name
    
    def get_translation_stats(self) -> dict:
        # ""Return translation/cache statistics.""
        stats = self.cache.get_cache_stats()
        stats['deepl_available'] = self.translator is not None
        return stats

