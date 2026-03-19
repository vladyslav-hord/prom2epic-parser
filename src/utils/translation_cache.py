# ""File-based cache for text translations.""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class TranslationCache:
    # ""Manage translation cache files.""
    
    def __init__(self, cache_dir: str = "data/other"):
        # ""Initialize translation cache storage.""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.categories_cache_file = self.cache_dir / "translated_categories.json"
        self.params_cache_file = self.cache_dir / "translated_params.json"
        self.general_cache_file = self.cache_dir / "translated_texts.json"
        
        self.categories_cache = self._load_cache(self.categories_cache_file)
        self.params_cache = self._load_cache(self.params_cache_file)
        self.general_cache = self._load_cache(self.general_cache_file)
    
    def _load_cache(self, cache_file: Path) -> Dict[str, Dict]:
        # ""Load cache content from disk.""
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Failed to load cache {cache_file}: {e}")
                return {}
        return {}
    
    def _save_cache(self, cache_data: Dict, cache_file: Path) -> None:
        # ""Save cache content to disk.""
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Failed to save cache {cache_file}: {e}")
    
    def get_category_translation(self, original_text: str) -> Optional[str]:
        # ""Get cached translation for a category name.""
        return self.categories_cache.get(original_text, {}).get('translation')
    
    def save_category_translation(self, original_text: str, translated_text: str, 
                                source_lang: str = 'ru', target_lang: str = 'uk') -> None:
        # ""Save category translation in cache.""
        self.categories_cache[original_text] = {
            'translation': translated_text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'timestamp': datetime.now().isoformat()
        }
        self._save_cache(self.categories_cache, self.categories_cache_file)
    
    def get_param_translation(self, param_name: str) -> Optional[str]:
        # ""Get cached translation for parameter name.""
        return self.params_cache.get(param_name, {}).get('translation')
    
    def save_param_translation(self, param_name: str, translated_name: str,
                             source_lang: str = 'ru', target_lang: str = 'uk') -> None:
        # ""Save parameter name translation in cache.""
        self.params_cache[param_name] = {
            'translation': translated_name,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'timestamp': datetime.now().isoformat()
        }
        self._save_cache(self.params_cache, self.params_cache_file)
    
    def get_general_translation(self, original_text: str) -> Optional[str]:
        # ""Get cached general text translation.""
        return self.general_cache.get(original_text, {}).get('translation')
    
    def save_general_translation(self, original_text: str, translated_text: str,
                               source_lang: str = 'ru', target_lang: str = 'uk') -> None:
        # ""Save general text translation in cache.""
        self.general_cache[original_text] = {
            'translation': translated_text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'timestamp': datetime.now().isoformat()
        }
        self._save_cache(self.general_cache, self.general_cache_file)
    
    def get_cache_stats(self) -> Dict[str, int]:
        # ""Return cache size statistics.""
        return {
            'categories': len(self.categories_cache),
            'params': len(self.params_cache),
            'general': len(self.general_cache),
            'total': len(self.categories_cache) + len(self.params_cache) + len(self.general_cache)
        }

