# ""Configuration for translation and data normalization.""

import os
from pathlib import Path


class TranslationConfig:
    # ""Translator configuration.""
    
    # DeepL API settings.
    DEEPL_API_KEY = os.getenv('DEEPL_API_KEY')
    
    # Cache directory.
    CACHE_DIR = "data/other"
    
    # Cache files.
    CATEGORIES_CACHE_FILE = "translated_categories.json"
    PARAMS_CACHE_FILE = "translated_params.json"
    GENERAL_CACHE_FILE = "translated_texts.json"
    
    # Translation settings.
    SOURCE_LANGUAGE = 'ru'  # Source language.
    TARGET_LANGUAGE = 'uk'  # Target language.
    
    # API rate limiting.
    MIN_REQUEST_INTERVAL = 0.1  # 100ms between requests.
    
    # Maximum text length for description translation.
    MAX_DESCRIPTION_LENGTH = 500
    
    # Minimum text length for language detection.
    MIN_TEXT_LENGTH = 3
    
    # Supported languages for detection.
    SUPPORTED_LANGUAGES = ['ru', 'uk', 'en', 'de', 'fr', 'es', 'it', 'pl']
    
    @classmethod
    def get_cache_dir_path(cls) -> Path:
        # ""Return cache directory path.""
        return Path(cls.CACHE_DIR)
    
    @classmethod
    def ensure_cache_dir(cls) -> None:
        # ""Create cache directory if it does not exist.""
        cache_dir = cls.get_cache_dir_path()
        cache_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def is_deepl_configured(cls) -> bool:
        # ""Check whether a DeepL API key is configured.""
        return bool(cls.DEEPL_API_KEY)
    
    @classmethod
    def get_cache_file_path(cls, cache_type: str) -> Path:
        """
        Return a cache file path.
        
        Args:
            cache_type: Cache type ('categories', 'params', 'general').
            
        Returns:
            Cache file path.
        """
        cache_dir = cls.get_cache_dir_path()
        
        if cache_type == 'categories':
            return cache_dir / cls.CATEGORIES_CACHE_FILE
        elif cache_type == 'params':
            return cache_dir / cls.PARAMS_CACHE_FILE
        elif cache_type == 'general':
            return cache_dir / cls.GENERAL_CACHE_FILE
        else:
            raise ValueError(f"Unknown cache type: {cache_type}")


# Create cache directory at import time.
TranslationConfig.ensure_cache_dir()

