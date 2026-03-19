# ""Multi-level cache for Epicentr attribute values.""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any


class AttributesCache:
    # ""Two-level attribute values cache (memory + file).""
    
    def __init__(self, cache_dir: str = "data/other/attributes_values"):
        """Initialize cache storage.

        Args:
            cache_dir: Directory where cache files are stored.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.memory_cache: Dict[str, Dict[str, str]] = {}
        
        logging.info(f"AttributesCache initialized, directory: {self.cache_dir}")
    
    def get(self, category_code: str, attribute_code: str) -> Optional[Dict[str, str]]:
        """Get attribute values from cache.

        Priority:
        1. In-memory cache
        2. Local file cache
        """
        if attribute_code == "brand":
            cache_key = attribute_code
        else:
            cache_key = f"{category_code}_{attribute_code}"
        
        if cache_key in self.memory_cache:
            if attribute_code == "brand":
                logging.debug(f"Attribute values for {attribute_code} found in memory")
            else:
                logging.debug(f"Attribute values for {attribute_code} in category {category_code} found in memory")
            return self.memory_cache[cache_key]
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    values = json.load(f)
                    self.memory_cache[cache_key] = values
                    if attribute_code == "brand":
                        logging.debug(f"Attribute values for {attribute_code} loaded from file")
                    else:
                        logging.debug(f"Attribute values for {attribute_code} in category {category_code} loaded from file")
                    return values
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to read cache file {cache_file}: {e}")
        
        return None
    
    def set(self, category_code: str, attribute_code: str, values: Dict[str, str]) -> None:
        # ""Store attribute values in memory and file cache.""
        if attribute_code == "brand":
            cache_key = attribute_code
        else:
            cache_key = f"{category_code}_{attribute_code}"
        
        self.memory_cache[cache_key] = values
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(values, f, ensure_ascii=False, indent=2)
            if attribute_code == "brand":
                logging.debug(f"Attribute values for {attribute_code} saved to file")
            else:
                logging.debug(f"Attribute values for {attribute_code} in category {category_code} saved to file")
        except IOError as e:
            logging.error(f"Failed to save cache file {cache_file}: {e}")
    
    def clear_memory_cache(self) -> None:
        # ""Clear in-memory cache only (keeps files).""
        self.memory_cache.clear()
        logging.debug("In-memory cache cleared")

