# ""Normalize product data and translate Russian text to Ukrainian.""

from typing import Dict, Any, Optional
from .language_translator import LanguageTranslator
from .brand_country_extractor import BrandCountryExtractor


class ProductDataNormalizer:
    # ""Normalize incoming product data.""
    
    def __init__(self, deepl_api_key: Optional[str] = None, cache_dir: str = "data/other"):
        # ""Initialize normalizer and related helpers.""
        self.translator = LanguageTranslator(deepl_api_key, cache_dir)
        self.brand_country_extractor = BrandCountryExtractor(cache_dir, deepl_api_key)
    
    def normalize_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        # ""Normalize product data and translate Russian text fields.""
        if not product_data:
            return product_data
        
        normalized_data = product_data.copy()
        
        if normalized_data.get('category_name'):
            normalized_data['category_name'] = self.translator.translate_category(
                normalized_data['category_name']
            )
        
        if normalized_data.get('params') and isinstance(normalized_data['params'], dict):
            normalized_params = {}
            
            for param_name, param_value in normalized_data['params'].items():
                translated_param_name = self.translator.translate_param_name(param_name)
                
                translated_param_value = param_value
                if isinstance(param_value, str) and param_value.strip():
                    if self.translator.is_russian_text(param_value):
                        translated_param_value = self.translator.translate_text(
                            param_value, 'ru', 'uk'
                        ) or param_value
                
                normalized_params[translated_param_name] = translated_param_value
            
            normalized_data['params'] = normalized_params
        
        # Normalize additional textual fields when UA variant is missing.
        if not normalized_data.get('name_ua') or not normalized_data['name_ua'].strip():
            if normalized_data.get('name') and self.translator.is_russian_text(normalized_data['name']):
                translated_name = self.translator.translate_text(normalized_data['name'], 'ru', 'uk')
                if translated_name:
                    normalized_data['name_ua'] = translated_name
        
        if not normalized_data.get('description_ua') or not normalized_data['description_ua'].strip():
            if normalized_data.get('description') and self.translator.is_russian_text(normalized_data['description']):
                description_text = normalized_data['description']
                if len(description_text) <= 500:
                    translated_description = self.translator.translate_text(description_text, 'ru', 'uk')
                    if translated_description:
                        normalized_data['description_ua'] = translated_description
        
        if normalized_data.get('vendor') and self.translator.is_russian_text(normalized_data['vendor']):
            translated_vendor = self.translator.translate_text(normalized_data['vendor'], 'ru', 'uk')
            if translated_vendor:
                normalized_data['vendor_ua'] = translated_vendor
            else:
                normalized_data['vendor_ua'] = normalized_data['vendor']
        else:
            normalized_data['vendor_ua'] = normalized_data.get('vendor', '')
        
        brand_country_info = self.brand_country_extractor.extract_brand_and_country(normalized_data)
        
        normalized_data['country'] = brand_country_info['country']
        normalized_data['country_ua'] = brand_country_info['country_ua']
        normalized_data['brand'] = brand_country_info['brand']
        
        return normalized_data
    
    def normalize_category_name(self, category_name: str) -> str:
        # ""Normalize category name.""
        return self.translator.translate_category(category_name)
    
    def normalize_param_names(self, params: Dict[str, str]) -> Dict[str, str]:
        # ""Normalize parameter names and values.""
        if not params:
            return params
        
        normalized_params = {}
        for param_name, param_value in params.items():
            translated_name = self.translator.translate_param_name(param_name)
            
            translated_value = param_value
            if isinstance(param_value, str) and self.translator.is_russian_text(param_value):
                translated_value = self.translator.translate_text(param_value, 'ru', 'uk') or param_value
            
            normalized_params[translated_name] = translated_value
        
        return normalized_params
    
    def get_normalization_stats(self) -> Dict[str, Any]:
        # ""Return normalization/translation stats.""
        return self.translator.get_translation_stats()
    
    def preload_common_translations(self) -> None:
        # ""Preload frequent category and parameter translations.""
        common_categories = [
            "Электроника", "Одежда", "Обувь", "Дом и сад", "Спорт и отдых",
            "Красота и здоровье", "Автотовары", "Детские товары", "Книги",
            "Мебель", "Бытовая техника", "Компьютеры", "Телефоны"
        ]
        
        common_params = [
            "Цвет", "Размер", "Материал", "Вес", "Производитель", "Страна производства",
            "Гарантия", "Тип", "Модель", "Бренд", "Состояние", "Мощность"
        ]
        
        print("Preloading translations...")
        
        for category in common_categories:
            self.translator.translate_category(category)
        
        for param in common_params:
            self.translator.translate_param_name(param)
        
        print("Preloading complete")

