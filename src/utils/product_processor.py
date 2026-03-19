# ""Full product pipeline: parsing, normalization, classification, attributes.""

import logging
from typing import Any, Dict, List, Optional

try:
    from ..parser import parse_single_product
    from ..category_matcher.core import CategoryMatcher
except ImportError:
    # Fallback for non-package execution.
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from parser import parse_single_product
    from category_matcher.core import CategoryMatcher

from .data_normalizer import ProductDataNormalizer
from .attributes_processor import AttributesProcessor
from .product_status_manager import NoPhotosProductsManager, RejectedProductsManager
from .xml_exporter import XMLExporter


class ProductProcessor:
    # ""Run full product processing pipeline.""
    
    def __init__(self, 
                 deepl_api_key: Optional[str] = None,
                 openai_api_key: Optional[str] = None,
                 epic_api_key: Optional[str] = None,
                 cache_dir: str = "data/other",
                 load_attributes: bool = True):
        # ""Initialize processing pipeline dependencies.""
        self.normalizer = ProductDataNormalizer(deepl_api_key, cache_dir)
        self.category_matcher = CategoryMatcher(
            openai_api_key=openai_api_key,
            cache_dir=cache_dir
        )
        self.attributes_processor = AttributesProcessor(data_dir=cache_dir)
        self.rejected_manager = RejectedProductsManager()
        self.no_photos_manager = NoPhotosProductsManager()
        self.xml_exporter = XMLExporter()
        self.load_attributes = load_attributes
        
        logging.info("ProductProcessor initialized with full pipeline")
    
    def process_single_product(self, xml_file_path: str, product_index: int = 0) -> Optional[Dict[str, Any]]:
        # ""Process a single product through all pipeline stages.""
        product_data = parse_single_product(xml_file_path, product_index)
        if not product_data:
            return None
        
        pictures = product_data.get("pictures", [])
        if not pictures or not any(pictures):
            self.no_photos_manager.add_no_photos(product_data, reason="No photos")
            self.no_photos_manager.save()
            logging.warning(f"Product {product_data.get('id', 'unknown')} skipped: no photos")
            return None
        
        normalized_data = self.normalizer.normalize_product_data(product_data)
        
        classification_result = self.category_matcher.classify(
            normalized_data, 
            load_attributes=self.load_attributes
        )
        
        if classification_result.get("rejected"):
            self.rejected_manager.add_rejected(
                normalized_data,
                reason=classification_result.get("reasoning", "Category not found")
            )
            self.rejected_manager.save()
            return {
                **normalized_data,
                "classification": classification_result,
                "epic_attributes": [],
                "rejected": True
            }
        
        epic_attributes = []
        selected_category = classification_result.get("selected_category")
        
        if selected_category and self.load_attributes:
            category_code = selected_category.get("id")
            category_name = selected_category.get("name", "")
            if category_code:
                try:
                    logging.info(f"Processing attributes for category: {category_name} (code: {category_code})")
                    
                    product_data_for_attrs = {
                        "name_ua": normalized_data.get("name_ua", ""),
                        "description_ua": normalized_data.get("description_ua", ""),
                        "brand": normalized_data.get("brand"),
                        "country_ua": normalized_data.get("country_ua"),
                        "category_name": category_name
                    }
                    
                    logging.debug(f"Attribute input data: brand={product_data_for_attrs.get('brand')}, country={product_data_for_attrs.get('country_ua')}")
                    
                    epic_attributes = self.attributes_processor.process_attributes_for_category(
                        category_code=category_code,
                        product_params=normalized_data.get("params", {}),
                        product_brand=normalized_data.get("brand"),
                        product_country=normalized_data.get("country_ua"),
                        product_data=product_data_for_attrs
                    )
                    
                    filled_count = len([a for a in epic_attributes if a.get("value")])
                    logging.info(f"Filled {filled_count} attributes out of {len(epic_attributes)} for category {category_name}")
                    
                    brand_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "brand"), None)
                    if not brand_attr or not brand_attr.get("value"):
                        logging.error(f"CRITICAL: Brand was not filled for product {normalized_data.get('id', 'unknown')}")
                    
                    country_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "country_of_origin"), None)
                    if not country_attr or not country_attr.get("value"):
                        logging.error(f"CRITICAL: Country was not filled for product {normalized_data.get('id', 'unknown')}")
                    elif not country_attr.get("valuecode"):
                        logging.warning(f"Country is filled ({country_attr.get('value')}), but code is missing for product {normalized_data.get('id', 'unknown')}")
                    
                except Exception as e:
                    logging.error(f"Attribute processing failed for product {normalized_data.get('id', 'unknown')}: {e}", exc_info=True)
                    epic_attributes = []
        
        result = {
            **normalized_data,
            "classification": classification_result,
            "epic_attributes": epic_attributes,
            "rejected": False
        }
        
        return result
    
    def preload_translations(self) -> None:
        # ""Preload translations to speed up processing.""
        self.normalizer.preload_common_translations()
    
    def get_processing_stats(self) -> Dict[str, Any]:
        # ""Return processing statistics.""
        return self.normalizer.get_normalization_stats()
    
