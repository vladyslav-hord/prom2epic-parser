# ""Extract product brand and country of origin.""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from .language_translator import LanguageTranslator


class BrandCountryExtractor:
    # ""Extract and normalize brand/country fields.""
    
    def __init__(self, data_dir: str = "data/other", deepl_api_key: Optional[str] = None):
        # ""Initialize extractor and optional translator.""
        self.data_dir = Path(data_dir)
        self.translator = LanguageTranslator(deepl_api_key, data_dir) if deepl_api_key else None
        
        self.countries = self._load_countries()
        self.brands = self._load_brands()
        
        # Domain default value; keep as is.
        self.default_country = "Китай"
        self.default_country_ua = "Китай"
        
        if self.translator:
            translated = self.translator.translate_text(self.default_country, 'ru', 'uk')
            if translated:
                self.default_country_ua = translated
    
    def _load_countries(self) -> Dict[str, str]:
        # ""Load countries dictionary.""
        countries_file = self.data_dir / "attributes_values" / "country_of_origin.json"
        
        if countries_file.exists():
            try:
                with open(countries_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Failed to load countries dictionary: {e}")
        
        return {}
    
    def _load_brands(self) -> Dict[str, str]:
        # ""Load brands dictionary.""
        brands_file = self.data_dir / "attributes_values" / "brand.json"
        
        if brands_file.exists():
            try:
                with open(brands_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Failed to load brands dictionary: {e}")
        
        return {}
    
    def extract_country(self, product_data: Dict) -> Tuple[str, str]:
        # ""Extract country of origin in source and UA variants.""
        country_origin = product_data.get('country_of_origin', '').strip()
        
        if country_origin:
            country_ua = country_origin
            
            if self.translator and self.translator.is_russian_text(country_origin):
                translated = self.translator.translate_text(country_origin, 'ru', 'uk')
                if translated:
                    country_ua = translated
            
            return country_origin, country_ua
        
        return self.default_country, self.default_country_ua
    
    def extract_brand(self, product_data: Dict) -> Optional[str]:
        # ""Extract product brand from source data.""
        vendor = product_data.get('vendor', '').strip()
        
        if vendor and vendor.lower() not in ['без бренда', 'без торговой марки', 'noname', 'no brand', '']:
            return vendor
        
        return None
    
    def extract_brand_and_country(self, product_data: Dict) -> Dict[str, str]:
        # ""Extract both brand and country for a product.""
        country, country_ua = self.extract_country(product_data)
        
        brand = self.extract_brand(product_data)
        
        return {
            'country': country,
            'country_ua': country_ua,
            'brand': brand
        }
    
    def normalize_country_name(self, country_name: str) -> str:
        # ""Normalize country name using dictionary and translation.""
        if not country_name:
            return self.default_country_ua
        
        for code, name in self.countries.items():
            if name.lower() == country_name.lower():
                return name
        
        if self.translator and self.translator.is_russian_text(country_name):
            translated = self.translator.translate_text(country_name, 'ru', 'uk')
            if translated:
                return translated
        
        return country_name
    
    def get_stats(self) -> Dict[str, int]:
        # ""Return basic extractor stats.""
        return {
            'countries_loaded': len(self.countries),
            'brands_loaded': len(self.brands),
            'default_country': self.default_country,
            'default_country_ua': self.default_country_ua,
            'translator_available': self.translator is not None
        }
