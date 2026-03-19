# ""Export processed products to Epicentr XML format.""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging


def indent_xml(elem: ET.Element, level: int = 0, indent: str = "  ") -> None:
    # ""Pretty-print XML element with indentation.""
    i = "\n" + level * indent
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + indent
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent_xml(child, level + 1, indent)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def escape_xml_text(text: str) -> str:
    # ""Escape XML-sensitive characters in text.""
    if not text:
        return ""
    
    text = str(text)
    # Prevent double escaping of already escaped XML entities.
    if "&amp;" in text or "&lt;" in text or "&gt;" in text or "&quot;" in text or "&apos;" in text:
        return text
    
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    
    return text


class XMLExporter:
    # ""Export products in Epicentr XML schema.""
    
    # Required fields for every category.
    MANDATORY_FIELDS = {
        "name_ua": "Назва товару (UA)",
        "available": "Наявність",
        "price": "Ціна",
        "pictures": "Фото товару",
        "country_ua": "Країна-виробник",
        "measure": "Одиниця виміру та кількість",
        "brand": "Бренд",
        "ratio": "Кратність",
        "category": "Категорія"
    }
    
    def __init__(self):
        # ""Initialize XML exporter.""
        logging.info("XMLExporter initialized")
    
    def export_single_product(self, product_data: Dict[str, Any]) -> str:
        """
        Export a single product to XML.
        
        Args:
            product_data: Processed product data.
            
        Returns:
            XML string containing one `offer` element.
        """
        product_data = self._fill_mandatory_fields(product_data)
        
        missing_fields = self._validate_mandatory_fields(product_data)
        if missing_fields:
            product_id = product_data.get('id', 'unknown')
            logging.error(
                f"PRODUCT {product_id}: Missing required fields: {', '.join(missing_fields.values())}. "
                f"The product will still be exported with a warning."
            )
        
        offer_elem = self._create_offer_element(product_data)
        
        indent_xml(offer_elem)
        
        rough_string = ET.tostring(offer_elem, encoding='unicode')
        
        return rough_string
    
    def _validate_mandatory_fields(self, product_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate presence of required product fields.
        
        Args:
            product_data: Product data.
            
        Returns:
            Dictionary {field_name: field_description} for missing fields.
        """
        missing_fields = {}
        product_id = product_data.get('id', 'unknown')
        
        if not product_data.get("name_ua") and not product_data.get("name"):
            missing_fields["name_ua"] = self.MANDATORY_FIELDS["name_ua"]
            logging.warning(f"PRODUCT {product_id}: missing product name (UA)")
        
        if not product_data.get("price"):
            missing_fields["price"] = self.MANDATORY_FIELDS["price"]
            logging.warning(f"PRODUCT {product_id}: missing price")
        
        pictures = product_data.get("pictures", [])
        if not pictures or not any(pictures):
            missing_fields["pictures"] = self.MANDATORY_FIELDS["pictures"]
            logging.warning(f"PRODUCT {product_id}: missing images")
        
        if not product_data.get("country_ua"):
            missing_fields["country_ua"] = self.MANDATORY_FIELDS["country_ua"]
            logging.warning(f"PRODUCT {product_id}: missing country of origin")
        
        epic_attributes = product_data.get("epic_attributes", [])
        measure_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "measure"), None)
        if not measure_attr or not measure_attr.get("value"):
            missing_fields["measure"] = self.MANDATORY_FIELDS["measure"]
            logging.warning(f"PRODUCT {product_id}: missing 'Одиниця виміру та кількість'")
        
        brand_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "brand"), None)
        if not brand_attr or not brand_attr.get("value"):
            missing_fields["brand"] = self.MANDATORY_FIELDS["brand"]
            logging.warning(f"PRODUCT {product_id}: missing brand")
        elif not brand_attr.get("valuecode"):
            logging.warning(f"PRODUCT {product_id}: brand is set ({brand_attr.get('value')}), but valuecode is missing")
        
        ratio_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "ratio"), None)
        if not ratio_attr or not ratio_attr.get("value"):
            missing_fields["ratio"] = self.MANDATORY_FIELDS["ratio"]
            logging.warning(f"PRODUCT {product_id}: missing ratio")
        
        classification = product_data.get("classification", {})
        selected_category = classification.get("selected_category")
        if not selected_category or not selected_category.get("id"):
            missing_fields["category"] = self.MANDATORY_FIELDS["category"]
            logging.warning(f"PRODUCT {product_id}: missing category")
        
        if product_data.get("available") is False:
            missing_fields["available"] = self.MANDATORY_FIELDS["available"]
            logging.warning(f"PRODUCT {product_id}: product is unavailable (available=false)")
        
        return missing_fields
    
    def _fill_mandatory_fields(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fill missing required fields with fallback values.
        
        Args:
            product_data: Product data.
            
        Returns:
            Product data with required fields populated.
        """
        product_id = product_data.get('id', 'unknown')
        epic_attributes = product_data.get("epic_attributes", [])
        
        if not product_data.get("name_ua") and not product_data.get("name"):
            product_data["name_ua"] = "Товар без назви"
            product_data["name"] = "Товар без названия"
            logging.warning(f"PRODUCT {product_id}: using fallback value for name_ua")
        elif not product_data.get("name_ua"):
            product_data["name_ua"] = product_data.get("name", "Товар без назви")
        
        if not product_data.get("price"):
            product_data["price"] = "0"
            logging.warning(f"PRODUCT {product_id}: using fallback value for price: 0")
        
        if not product_data.get("price_old"):
            product_data["price_old"] = "0"
        
        if not product_data.get("pictures"):
            product_data["pictures"] = []
            logging.warning(f"PRODUCT {product_id}: no images")
        
        if not product_data.get("country_ua"):
            product_data["country_ua"] = "Китай"
            logging.warning(f"PRODUCT {product_id}: using fallback value for country_ua: Китай")
            country_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "country_of_origin"), None)
            if not country_attr:
                epic_attributes.append({
                    "name": "Країна-виробник",
                    "paramcode": "country_of_origin",
                    "valuecode": "chn",
                    "value": "Китай",
                    "type": "select",
                    "is_required": True
                })
                product_data["epic_attributes"] = epic_attributes
                logging.info(f"PRODUCT {product_id}: added country_of_origin attribute with fallback value")
        
        if product_data.get("available") is None:
            product_data["available"] = True
        
        measure_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "measure"), None)
        if not measure_attr or not measure_attr.get("value"):
            measure_valuecode = "measure_pcs"
            measure_value = "шт."
            
            if not measure_attr:
                epic_attributes.append({
                    "name": "Одиниця виміру та кількість",
                    "paramcode": "measure",
                    "valuecode": measure_valuecode,
                    "value": measure_value,
                    "type": "select",
                    "is_required": True
                })
                product_data["epic_attributes"] = epic_attributes
                logging.warning(f"PRODUCT {product_id}: added measure attribute with fallback value: {measure_value}")
        
        brand_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "brand"), None)
        if not brand_attr or not brand_attr.get("value"):
            logging.error(f"PRODUCT {product_id}: CRITICAL - brand is not filled. This must be handled in attributes_filler.")
        
        ratio_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "ratio"), None)
        if not ratio_attr or not ratio_attr.get("value"):
            if not ratio_attr:
                epic_attributes.append({
                    "name": "Кратність",
                    "paramcode": "ratio",
                    "valuecode": None,
                    "value": "1.0",
                    "type": "float",
                    "is_required": True
                })
                product_data["epic_attributes"] = epic_attributes
                logging.warning(f"PRODUCT {product_id}: added ratio attribute with fallback value: 1.0")
            else:
                ratio_attr["value"] = "1.0"
                logging.warning(f"PRODUCT {product_id}: updated ratio attribute with fallback value: 1.0")
        
        return product_data
    
    def export_products(self, products_list: List[Dict[str, Any]], 
                       output_file: Optional[str] = None,
                       append: bool = False) -> str:
        """
        Export a list of products to an XML catalog.
        
        Args:
            products_list: List of processed products.
            output_file: Optional output file path.
            append: If True, append to an existing file instead of overwriting.
            
        Returns:
            XML string with the product catalog.
        """
        existing_offers = []
        if append and output_file:
            from pathlib import Path
            output_path = Path(output_file)
            if output_path.exists():
                try:
                    tree = ET.parse(output_path)
                    root = tree.getroot()
                    offers_elem = root.find(".//offers")
                    if offers_elem is not None:
                        existing_offers = list(offers_elem)
                        logging.info(f"Loaded {len(existing_offers)} existing products from {output_file}")
                except Exception as e:
                    logging.warning(f"Failed to load existing products from {output_file}: {e}")
        
        catalog = ET.Element("yml_catalog")
        catalog.set("date", datetime.now().strftime("%Y-%m-%d %H:%M"))
        
        offers = ET.SubElement(catalog, "offers")
        
        for offer_elem in existing_offers:
            offers.append(offer_elem)
        
        new_count = 0
        for product_data in products_list:
            if product_data.get("rejected"):
                continue
            
            offer_elem = self._create_offer_element(product_data)
            offers.append(offer_elem)
            new_count += 1
        
        indent_xml(catalog)
        
        rough_string = ET.tostring(catalog, encoding='unicode')
        
        xml_string = '<?xml version=\'1.0\' encoding=\'utf-8\'?>\n' + rough_string
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(xml_string)
            total_count = len(existing_offers) + new_count
            logging.info(f"Exported {new_count} new products; total in file: {total_count}")
        
        return xml_string
    
    def _create_offer_element(self, product_data: Dict[str, Any]) -> ET.Element:
        """
        Create an XML `offer` element for a product.
        
        Args:
            product_data: Processed product data.
            
        Returns:
            XML `offer` element.
        """
        product_id = product_data.get("id", "unknown")
        logging.debug(f"Creating XML element for product {product_id}")
        
        offer = ET.Element("offer")
        offer.set("id", str(product_id))
        
        available = product_data.get("available", True)
        offer.set("available", "true" if available else "false")
        logging.debug(f"Product {product_id}: available={available}")
        
        price = product_data.get("price", "0")
        price_elem = ET.SubElement(offer, "price")
        price_elem.text = str(price)
        
        price_old = product_data.get("price_old", "0")
        price_old_elem = ET.SubElement(offer, "price_old")
        price_old_elem.text = str(price_old)
        
        selected_category = product_data.get("classification", {}).get("selected_category")
        if selected_category:
            category_code = selected_category.get("id", "")
            category_name = selected_category.get("name", "")
            
            category_elem = ET.SubElement(offer, "category")
            category_elem.set("code", str(category_code))
            category_elem.text = category_name
            
            attribute_set_elem = ET.SubElement(offer, "attribute_set")
            attribute_set_elem.set("code", str(category_code))
            attribute_set_elem.text = category_name
        
        name_ru = product_data.get("name", "")
        name_ua = product_data.get("name_ua", "") or name_ru or "Товар без назви"
        
        if not name_ua:
            name_ua = "Товар без назви"
        if not name_ru:
            name_ru = "Товар без названия"
        
        name_ru_elem = ET.SubElement(offer, "name")
        name_ru_elem.set("lang", "ru")
        name_ru_elem.text = name_ru
        logging.debug(f"Product {product_id}: name_ru={name_ru[:50]}...")
        
        name_ua_elem = ET.SubElement(offer, "name")
        name_ua_elem.set("lang", "ua")
        name_ua_elem.text = name_ua
        logging.debug(f"Product {product_id}: name_ua={name_ua[:50]}...")
        
        pictures = product_data.get("pictures", [])
        pictures_count = 0
        for picture_url in pictures:
            if picture_url:
                picture_elem = ET.SubElement(offer, "picture")
                picture_elem.text = picture_url
                pictures_count += 1
        logging.debug(f"Product {product_id}: added {pictures_count} images")
        if pictures_count == 0:
            logging.warning(f"Product {product_id}: no images")
        
        description_ru = product_data.get("description", "")
        description_ua = product_data.get("description_ua", "") or description_ru
        
        description_ru_elem = ET.SubElement(offer, "description")
        description_ru_elem.set("lang", "ru")
        description_ru_elem.text = escape_xml_text(description_ru)
        
        description_ua_elem = ET.SubElement(offer, "description")
        description_ua_elem.set("lang", "ua")
        description_ua_elem.text = escape_xml_text(description_ua)
        
        epic_attributes = product_data.get("epic_attributes", [])
        brand_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "brand"), None)
        
        if brand_attr and brand_attr.get("value"):
            vendor_elem = ET.SubElement(offer, "vendor")
            if brand_attr.get("valuecode"):
                vendor_elem.set("code", brand_attr["valuecode"])
                logging.debug(f"Product {product_id}: brand={brand_attr.get('value')} (code: {brand_attr['valuecode']})")
            else:
                logging.warning(f"Product {product_id}: brand is set ({brand_attr.get('value')}), but no valuecode")
            vendor_elem.text = brand_attr.get("value", "")
        else:
            logging.error(f"Product {product_id}: CRITICAL - brand is missing. It must be filled in attributes_filler.")
            vendor_elem = ET.SubElement(offer, "vendor")
            vendor_elem.text = "Unknown"
        
        country_ua = product_data.get("country_ua") or "Китай"
        country_attr = next((attr for attr in epic_attributes if attr.get("paramcode") == "country_of_origin"), None)
        country_code = ""
        if country_attr and country_attr.get("valuecode"):
            country_code = country_attr["valuecode"]
        elif country_ua.lower() in ["китай", "china"]:
            country_code = "chn"
        
        country_elem = ET.SubElement(offer, "country_of_origin")
        if country_code:
            country_elem.set("code", country_code)
            logging.debug(f"Product {product_id}: country={country_ua} (code: {country_code})")
        else:
            logging.warning(f"Product {product_id}: country is set ({country_ua}), but code is missing")
        country_elem.text = country_ua
        
        params_count = 0
        for attr in epic_attributes:
            paramcode = attr.get("paramcode", "")
            attr_name = attr.get("name", "")
            attr_value = attr.get("value")
            attr_type = attr.get("type", "")
            valuecode = attr.get("valuecode")
            
            if not attr_value or paramcode in ("brand", "country_of_origin"):
                if paramcode in ("brand", "country_of_origin") and not attr_value:
                    logging.warning(f"Product {product_id}: attribute {paramcode} ({attr_name}) has no value")
                continue
            
            if paramcode == "measure" and not attr_value:
                logging.warning(f"Product {product_id}: required parameter 'Одиниця виміру та кількість' is not filled")
            if paramcode == "ratio" and not attr_value:
                logging.warning(f"Product {product_id}: required parameter 'Кратність' is not filled")
            
            param_elem = ET.SubElement(offer, "param")
            param_elem.set("name", attr_name)
            param_elem.set("paramcode", str(paramcode))
            
            if attr_type in ("select", "multiselect") and valuecode:
                param_elem.set("valuecode", str(valuecode))
                logging.debug(f"Product {product_id}: parameter {paramcode} ({attr_name}) = {attr_value} (code: {valuecode})")
            elif attr_type in ("select", "multiselect") and not valuecode:
                logging.warning(f"Product {product_id}: parameter {paramcode} ({attr_name}) of type {attr_type} has no valuecode")
            else:
                logging.debug(f"Product {product_id}: parameter {paramcode} ({attr_name}) = {attr_value}")
            
            param_elem.text = str(attr_value)
            params_count += 1
        
        logging.debug(f"Product {product_id}: added {params_count} parameters")
        
        width = product_data.get("width")
        height = product_data.get("height")
        
        if width:
            width_elem = ET.SubElement(offer, "width")
            width_elem.text = str(width)
        
        if height:
            height_elem = ET.SubElement(offer, "height")
            height_elem.text = str(height)
        
        return offer

