# ""Loader for required Epicentr category attributes.""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .epic_api_client import EpicAPIClient
from .attributes_cache import AttributesCache


class AttributesLoader:
    # ""Load required attributes and their dictionary values.""
    
    def __init__(self,
                 attributes_file: str = "data/other/epic_required_attributes.json",
                 cache_dir: str = "data/other/attributes_values",
                 api_key: Optional[str] = None,
                 max_workers: int = 10):
        # ""Initialize the attributes loader.""
        self.attributes_file = Path(attributes_file)
        self.api_client = EpicAPIClient(api_key=api_key)
        self.cache = AttributesCache(cache_dir=cache_dir)
        self.max_workers = max_workers
        
        self.required_attributes: Dict[str, List[Dict[str, Any]]] = {}
        self._load_required_attributes()
        
        logging.info(f"AttributesLoader initialized (max_workers={max_workers})")
    
    def _load_required_attributes(self) -> None:
        # ""Load required attributes from file.""
        try:
            with open(self.attributes_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for category_data in data:
                category_code = category_data.get("code")
                if category_code:
                    self.required_attributes[category_code] = category_data.get("attributes", [])
            
            logging.info(f"Loaded {len(self.required_attributes)} categories with attributes")
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Failed to load attributes file {self.attributes_file}: {e}")
            raise
    
    def get_category_attributes(self, category_code: str) -> List[Dict[str, Any]]:
        # ""Return required attributes for a category.""
        attributes = self.required_attributes.get(category_code, [])
        
        if not attributes:
            logging.warning(f"Attributes not found for category {category_code}")
        
        return attributes
    
    def get_attribute_values(self,
                            category_code: str,
                            attribute_code: str,
                            use_cache: bool = True) -> Dict[str, str]:
        # ""Return attribute values for select/multiselect attributes.""
        if use_cache:
            cached_values = self.cache.get(category_code, attribute_code)
            if cached_values is not None:
                return cached_values
        
        try:
            option_items = self.api_client.get_all_attribute_options(
                category_code, attribute_code, max_workers=self.max_workers
            )
            
            values = {}
            for item in option_items:
                option_code = item.get("code", "")
                if option_code:
                    value = self.api_client.extract_option_value(item)
                    values[option_code] = value
            
            if values:
                self.cache.set(category_code, attribute_code, values)
            
            return values
            
        except Exception as e:
            logging.error(f"Failed to load values for attribute {attribute_code} in category {category_code}: {e}")
            if use_cache:
                cached_values = self.cache.get(category_code, attribute_code)
                if cached_values:
                    logging.warning(f"Using stale cached values for attribute {attribute_code} in category {category_code}")
                    return cached_values
            return {}
    
    def get_category_attributes_with_values(self,
                                           category_code: str,
                                           load_values: bool = True) -> List[Dict[str, Any]]:
        # ""Return category attributes with optionally loaded dictionary values.""
        attributes = self.get_category_attributes(category_code)
        
        if not load_values:
            return attributes
        
        attrs_to_load = [
            attr for attr in attributes
            if attr.get("type") in ("select", "multiselect") and attr.get("code")
        ]
        
        if not attrs_to_load:
            return attributes
        
        logging.info(f"Loading values in parallel for {len(attrs_to_load)} attributes in category {category_code}")
        
        def load_attr_values(attr: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
            # ""Load values for a single attribute.""
            attr_code = attr.get("code", "")
            try:
                values = self.get_attribute_values(category_code, attr_code)
                return attr_code, values
            except Exception as e:
                logging.warning(f"Could not load values for attribute {attr_code}: {e}")
                return attr_code, {}
        
        attr_values_map = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_attr = {
                executor.submit(load_attr_values, attr): attr.get("code", "")
                for attr in attrs_to_load
            }
            
            for future in as_completed(future_to_attr):
                attr_code = future_to_attr[future]
                try:
                    loaded_attr_code, values = future.result()
                    attr_values_map[loaded_attr_code] = values
                except Exception as e:
                    logging.error(f"Failed processing values for attribute {attr_code}: {e}")
                    attr_values_map[attr_code] = {}
        
        result = []
        for attr in attributes:
            attr_dict = attr.copy()
            attr_code = attr.get("code", "")
            
            if attr_code in attr_values_map:
                attr_dict["values"] = attr_values_map[attr_code]
            elif attr.get("type") in ("select", "multiselect"):
                attr_dict["values"] = {}
            
            result.append(attr_dict)
        
        logging.info(f"Loaded values for {len(attrs_to_load)} attributes in category {category_code}")
        return result
    
    def get_attribute_name_ua(self, attribute: Dict[str, Any]) -> str:
        # ""Extract Ukrainian attribute title with Russian fallback.""
        translations = attribute.get("translations", [])
        
        for trans in translations:
            if trans.get("languageCode") == "ua":
                return trans.get("title", "")
        
        for trans in translations:
            if trans.get("languageCode") == "ru":
                return trans.get("title", "")
        
        return attribute.get("code", "")

