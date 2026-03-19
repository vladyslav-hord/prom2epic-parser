# ""Attribute processor for mapping product params to Epicentr attributes.""

import logging
from typing import Any, Dict, List, Optional

from .attributes_loader import AttributesLoader
from .attributes_filler import AttributesFiller


class AttributesProcessor:
    # ""Process and map product attributes.""
    
    def __init__(self, 
                 attributes_loader: Optional[AttributesLoader] = None,
                 attributes_filler: Optional[AttributesFiller] = None,
                 data_dir: str = "data/other"):
        # ""Initialize the attributes processor.""
        self.attributes_loader = attributes_loader or AttributesLoader()
        self.attributes_filler = attributes_filler or AttributesFiller(data_dir=data_dir)
        logging.info("AttributesProcessor initialized")
    
    def process_attributes_for_category(self,
                                      category_code: str,
                                      product_params: Dict[str, str],
                                      product_brand: Optional[str] = None,
                                      product_country: Optional[str] = None,
                                      product_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # ""Fill attributes for a selected category.""
        epic_attributes = self.attributes_loader.get_category_attributes_with_values(
            category_code, load_values=True
        )
        
        if not epic_attributes:
            logging.warning(f"Attributes not found for category {category_code}")
            return []
        
        if product_data is None:
            product_data = {}
        
        if product_brand:
            product_data["brand"] = product_brand
        if product_country:
            product_data["country_ua"] = product_country
        
        filled_attributes = self.attributes_filler.fill_attributes(
            epic_attributes=epic_attributes,
            product_data=product_data,
            product_params=product_params
        )
        
        return filled_attributes

