# ""Module for parsing products from a Prom.ua XML file.""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Iterator
from pathlib import Path


class ProductData:
    # ""Data structure for a product.""
    
    def __init__(self):
        self.id: str = ""
        self.name: str = ""
        self.name_ua: str = ""
        self.category_id: str = ""
        self.category_name: str = ""
        self.description: str = ""
        self.description_ua: str = ""
        self.price: str = ""
        self.price_old: str = ""
        self.url: str = ""
        self.vendor: str = ""
        self.country_of_origin: str = ""
        self.pictures: List[str] = []
        self.params: Dict[str, str] = {}
    
    def to_dict(self) -> Dict:
        # ""Convert object data to a dictionary.""
        return {
            "id": self.id,
            "name": self.name,
            "name_ua": self.name_ua,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "description": self.description,
            "description_ua": self.description_ua,
            "price": self.price,
            "price_old": self.price_old,
            "url": self.url,
            "vendor": self.vendor,
            "country_of_origin": self.country_of_origin,
            "pictures": self.pictures,
            "params": self.params
        }


class PromXMLParser:
    # ""Parser for Prom.ua XML files.""
    
    def __init__(self, xml_file_path: str):
        """
        Initialize parser.
        
        Args:
            xml_file_path: Path to XML file.
        """
        self.xml_file_path = Path(xml_file_path)
        self.categories: Dict[str, str] = {}
        self._load_categories()
    
    def _load_categories(self) -> None:
        # ""Load categories from XML file.""
        try:
            # Use iterparse to reduce memory usage.
            for event, elem in ET.iterparse(self.xml_file_path, events=('start', 'end')):
                if event == 'end' and elem.tag == 'category':
                    category_id = elem.get('id', '')
                    category_name = elem.text or ''
                    if category_id and category_name:
                        self.categories[category_id] = category_name
                    elem.clear()
                elif event == 'end' and elem.tag == 'categories':
                    # Finished processing categories.
                    break
        except ET.ParseError as e:
            raise ValueError(f"XML parsing error: {e}")
    
    def get_total_offers_count(self) -> int:
        """
        Count total number of products in XML file.
        
        Returns:
            int: Product count.
        """
        count = 0
        try:
            for event, elem in ET.iterparse(self.xml_file_path, events=('end',)):
                if elem.tag == 'offer':
                    count += 1
                    elem.clear()
        except ET.ParseError as e:
            raise ValueError(f"XML parsing error while counting products: {e}")
        
        return count
    
    def parse_offer_by_index(self, product_index: int) -> Optional[ProductData]:
        """
        Parse one product by index.
        
        Args:
            product_index: Product index (starting from 0).
            
        Returns:
            ProductData: Product data or None if not found.
        """
        for i, product in enumerate(self.parse_products()):
            if i == product_index:
                return product
        
        return None
    
    def parse_products(self) -> Iterator[ProductData]:
        """
        Generator for sequential product parsing.
        
        Yields:
            ProductData: Data for one product.
        """
        try:
            context = ET.iterparse(self.xml_file_path, events=('start', 'end'))
            context = iter(context)
            event, root = next(context)
            
            for event, elem in context:
                if event == 'end' and elem.tag == 'offer':
                    product = self._parse_single_offer(elem)
                    if product:
                        yield product
                    elem.clear()
                    root.clear()
                    
        except ET.ParseError as e:
            raise ValueError(f"XML parsing error: {e}")
    
    def _parse_single_offer(self, offer_elem: ET.Element) -> Optional[ProductData]:
        """
        Parse one offer element.
        
        Args:
            offer_elem: XML offer element.
            
        Returns:
            ProductData or None if product is unavailable.
        """
        # Skip unavailable products.
        if offer_elem.get('available') != 'true':
            return None
        
        product = ProductData()
        
        product.id = offer_elem.get('id', '')
        
        for child in offer_elem:
            tag = child.tag
            text = (child.text or '').strip()
            
            if tag == 'name':
                product.name = text
            elif tag == 'name_ua':
                product.name_ua = text
            elif tag == 'categoryId':
                product.category_id = text
                product.category_name = self.categories.get(text, '')
            elif tag == 'description':
                product.description = text
            elif tag == 'description_ua':
                product.description_ua = text
            elif tag == 'price':
                product.price = text
            elif tag == 'oldprice':
                product.price_old = text
            elif tag == 'url':
                product.url = text
            elif tag == 'vendor':
                product.vendor = text
            elif tag == 'country_of_origin':
                product.country_of_origin = text
            elif tag == 'picture':
                if text:
                    product.pictures.append(text)
            elif tag == 'param':
                param_name = child.get('name', '')
                param_unit = child.get('unit', '')
                param_value = text
                
                # Append unit to value when present.
                if param_unit:
                    param_value = f"{param_value} {param_unit}"
                
                if param_name and param_value:
                    product.params[param_name] = param_value
        
        return product


def parse_single_product(xml_file_path: str, product_index: int = 0) -> Optional[Dict]:
    """
    Parse one product by index.
    
    Args:
        xml_file_path: Path to XML file.
        product_index: Product index (starting from 0).
        
    Returns:
        Product data dictionary or None if not found.
    """
    parser = PromXMLParser(xml_file_path)
    
    for i, product in enumerate(parser.parse_products()):
        if i == product_index:
            return product.to_dict()
    
    return None


def get_products_iterator(xml_file_path: str) -> Iterator[Dict]:
    """
    Return an iterator for sequential product reads.
    
    Args:
        xml_file_path: Path to XML file.
        
    Yields:
        Dict: Product data as dictionary.
    """
    parser = PromXMLParser(xml_file_path)
    
    for product in parser.parse_products():
        yield product.to_dict()

