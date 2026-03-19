# ""Fill required Epicentr attributes from product data.""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .value_matcher import ValueMatcher
from .unit_converter import UnitConverter
from .llm_attributes_helper import LLMAttributesHelper


class AttributesFiller:
    # ""Fill required attributes using input data and LLM fallbacks.""
    
    def __init__(self,
                 value_matcher: Optional[ValueMatcher] = None,
                 unit_converter: Optional[UnitConverter] = None,
                 llm_helper: Optional[LLMAttributesHelper] = None,
                 data_dir: str = "data/other"):
        # ""Initialize attribute filling dependencies.""
        self.value_matcher = value_matcher or ValueMatcher()
        self.unit_converter = unit_converter or UnitConverter()
        self.llm_helper = llm_helper or LLMAttributesHelper()
        self.data_dir = Path(data_dir)
        
        # Load country dictionary used to resolve option codes.
        self.countries_dict = self._load_countries_dict()
        
        logging.info("AttributesFiller initialized")
    
    def _load_countries_dict(self) -> Dict[str, str]:
        # ""Load country dictionary from `country_of_origin.json`.""
        countries_file = self.data_dir / "attributes_values" / "country_of_origin.json"
        
        if countries_file.exists():
            try:
                with open(countries_file, 'r', encoding='utf-8') as f:
                    countries_data = json.load(f)
                    # Build reverse lookup map {name: code}.
                    countries_dict = {}
                    for code, name in countries_data.items():
                        countries_dict[name.lower()] = code
                        countries_dict[name] = code
                    logging.info(f"Loaded {len(countries_dict)} country dictionary entries")
                    return countries_dict
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Failed to load countries dictionary: {e}")
        
        logging.warning("Countries dictionary not found; country codes will be resolved from attribute dictionaries only")
        return {}
    
    def fill_attributes(self,
                       epic_attributes: List[Dict[str, Any]],
                       product_data: Dict[str, Any],
                       product_params: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Fill required product attributes.
        
        Args:
            epic_attributes: Epicentr attributes with loaded metadata/values.
            product_data: Product data (name_ua, description_ua, brand, country_ua, category_name).
            product_params: Product parameters from the input file (usually in Ukrainian).
            
        Returns:
            A list of filled attributes in the format:
            [
                {
                    "name": "Потужність",
                    "paramcode": "103",
                    "valuecode": "1500",
                    "value": "1500 Вт",
                    "type": "select",
                    "is_required": true
                },
                ...
            ]
        """
        result = []
        filled_values = {}
        
        product_name_ua = product_data.get("name_ua", "")
        product_description_ua = product_data.get("description_ua", "")
        product_brand = product_data.get("brand")
        product_country = product_data.get("country_ua")
        category_name = product_data.get("category_name", "")
        
        logging.info(f"Starting attribute filling for product: {product_name_ua[:50]}...")
        logging.debug(f"Product data: brand={product_brand}, country={product_country}, category={category_name}")
        logging.debug(f"Total attributes to fill: {len(epic_attributes)}")
        
        attributes_to_fill = []
        attributes_missing = []
        
        for epic_attr in epic_attributes:
            attr_code = epic_attr.get("code", "")
            attr_type = epic_attr.get("type", "")
            is_required = epic_attr.get("isRequired", False)
            
            if not is_required:
                attr_result = self._create_empty_attr_result(epic_attr)
                result.append(attr_result)
                continue
            
            matched_param = self._find_param_in_input(epic_attr, product_params)
            
            if matched_param:
                attributes_to_fill.append((epic_attr, matched_param))
            else:
                attributes_missing.append(epic_attr)
        
        logging.info(f"Found {len(attributes_to_fill)} attributes in the input file")
        for epic_attr, matched_param in attributes_to_fill:
            attr_code = epic_attr.get("code", "")
            attr_name = self._get_attr_name_ua(epic_attr)
            logging.debug(f"Filling attribute from input: {attr_code} ({attr_name}) = {matched_param.get('value', '')}")
            filled_attr = self._fill_attribute_from_input(
                epic_attr, matched_param, filled_values
            )
            if filled_attr:
                result.append(filled_attr)
                logging.debug(f"Attribute {attr_code} was successfully filled from input")
            else:
                logging.warning(f"Failed to fill attribute {attr_code} from input")
        
        if attributes_missing:
            missing_attr_names = [self._get_attr_name_ua(attr) for attr in attributes_missing]
            logging.info(f"Requesting ChatGPT values for {len(attributes_missing)} missing attributes: {', '.join(missing_attr_names[:5])}...")
            
            missing_attr_codes = {attr.get("code", "") for attr in attributes_missing if attr.get("code")}
            
            llm_suggestions = self.llm_helper.suggest_attribute_values(
                attributes=attributes_missing,
                product_name_ua=product_name_ua,
                product_description_ua=product_description_ua,
                product_params=product_params,
                category_name=category_name,
                existing_values=filled_values
            )
            
            logging.info(f"ChatGPT suggested values for {len(llm_suggestions)} attributes")
            
            received_attr_codes = set(llm_suggestions.keys())
            missing_in_response = missing_attr_codes - received_attr_codes
            
            if missing_in_response:
                logging.warning(
                    f"ChatGPT skipped {len(missing_in_response)} attributes: {', '.join(missing_in_response)}. "
                    f"Fallback values will be used."
                )
            
            for epic_attr in attributes_missing:
                attr_code = epic_attr.get("code", "")
                suggested_value = llm_suggestions.get(attr_code)
                
                if suggested_value:
                    filled_attr = self._fill_attribute_from_suggestion(
                        epic_attr, suggested_value, filled_values
                    )
                    if filled_attr:
                        result.append(filled_attr)
                    else:
                        logging.warning(f"Failed to fill attribute {attr_code} from ChatGPT suggestion; using fallback")
                        filled_attr = self._fill_attribute_fallback(epic_attr, filled_values, suggested_value=suggested_value)
                        if filled_attr:
                            result.append(filled_attr)
                else:
                    attr_name = self._get_attr_name_ua(epic_attr)
                    logging.warning(
                        f"ChatGPT did not suggest a value for attribute {attr_code} ({attr_name}); "
                        f"using semantic-search fallback"
                    )
                    filled_attr = self._fill_attribute_fallback(epic_attr, filled_values)
                    if filled_attr:
                        result.append(filled_attr)
        
        brand_attr = next((attr for attr in epic_attributes if attr.get("code") == "brand"), None)
        
        if not brand_attr:
            logging.warning("The 'brand' attribute was not found in category attributes; creating it manually")
            brand_file = self.data_dir / "attributes_values" / "brand.json"
            brand_values = {}
            if brand_file.exists():
                try:
                    with open(brand_file, 'r', encoding='utf-8') as f:
                        brand_values = json.load(f)
                    logging.info(f"Loaded brand dictionary from file: {len(brand_values)} brands")
                except Exception as e:
                    logging.error(f"Failed to load brand dictionary from file: {e}")
            else:
                logging.error(f"Brand dictionary file not found: {brand_file}")
            
            brand_attr = {
                "code": "brand",
                "type": "select",
                "isRequired": True,
                "translations": [{"languageCode": "ua", "title": "Бренд"}],
                "values": brand_values if brand_values else {}
            }
            epic_attributes.append(brand_attr)
        
        if brand_attr:
            existing_brand = next((attr for attr in result if attr.get("paramcode") == "brand"), None)
            if not existing_brand or not existing_brand.get("value"):
                if not product_brand:
                    logging.info("Brand is not provided in product data; requesting ChatGPT suggestion...")
                    suggested_brand = self.llm_helper.suggest_brand(
                        product_name_ua, product_description_ua, product_params, category_name
                    )
                    brand_filled = False
                    
                    if suggested_brand:
                        if suggested_brand.lower() not in ["не вказано", "без бренда", "noname", "no brand", ""]:
                            if suggested_brand == "USE_FALLBACK_SEARCH":
                                logging.info("ChatGPT returned USE_FALLBACK_SEARCH; using semantic search on product name")
                            else:
                                filled_attr = self._fill_brand_attribute(brand_attr, suggested_brand, filled_values)
                                if filled_attr:
                                    result = [attr for attr in result if attr.get("paramcode") != "brand"]
                                    result.append(filled_attr)
                                    logging.info(f"Brand filled: {suggested_brand}")
                                    brand_filled = True
                        else:
                            logging.warning(f"ChatGPT suggested an invalid brand value: {suggested_brand}; using fallback")
                    
                    if not brand_filled and (not suggested_brand or suggested_brand == "USE_FALLBACK_SEARCH" or 
                                           (suggested_brand and suggested_brand.lower() in ["не вказано", "без бренда", "noname", "no brand", ""])):
                        logging.warning("ChatGPT did not provide a valid brand; using semantic search on product name")
                        values_dict = brand_attr.get("values", {})
                        if values_dict:
                            code, text, score = self.value_matcher.find_best_match(product_name_ua, values_dict)
                            filled_attr = self._fill_brand_attribute(brand_attr, text, filled_values)
                            if filled_attr:
                                filled_attr["valuecode"] = code
                                filled_attr["value"] = text
                                result = [attr for attr in result if attr.get("paramcode") != "brand"]
                                result.append(filled_attr)
                                logging.warning(f"Brand found via semantic search in product name: {text} (code: {code}, score: {score:.3f})")
                        else:
                            logging.error(f"CRITICAL: Brand dictionary is empty. Cannot run semantic search for product {product_name_ua[:50]}...")
                            filled_attr = self._create_base_attr_result(brand_attr)
                            filled_attr["value"] = "Unknown"
                            result = [attr for attr in result if attr.get("paramcode") != "brand"]
                            result.append(filled_attr)
                            logging.error("Created brand attribute with fallback value 'Unknown' (brand dictionary unavailable)")
                else:
                    filled_attr = self._fill_brand_attribute(brand_attr, product_brand, filled_values)
                    if filled_attr:
                        result = [attr for attr in result if attr.get("paramcode") != "brand"]
                        result.append(filled_attr)
                        logging.info(f"Brand filled from product data: {product_brand}")
        
        country_attr = next((attr for attr in epic_attributes if attr.get("code") == "country_of_origin"), None)
        if product_country:
            existing_country = next((attr for attr in result if attr.get("paramcode") == "country_of_origin"), None)
            if not existing_country or not existing_country.get("value"):
                if country_attr:
                    filled_attr = self._fill_country_attribute(country_attr, product_country, filled_values)
                    if filled_attr:
                        result = [attr for attr in result if attr.get("paramcode") != "country_of_origin"]
                        result.append(filled_attr)
                        logging.info(f"Country of origin filled: {product_country}")
                else:
                    logging.warning("Attribute country_of_origin is missing from category attributes, but country is mandatory. Creating it manually.")
                    country_attr_manual = {
                        "code": "country_of_origin",
                        "type": "select",
                        "isRequired": True,
                        "translations": [{"languageCode": "ua", "title": "Країна-виробник"}]
                    }
                    filled_attr = self._fill_country_attribute(country_attr_manual, product_country, filled_values)
                    if filled_attr:
                        result = [attr for attr in result if attr.get("paramcode") != "country_of_origin"]
                        result.append(filled_attr)
                        logging.info(f"Country of origin filled (manual attribute): {product_country}")
            else:
                logging.debug(f"Country of origin already filled: {existing_country.get('value')}")
        else:
            logging.warning("Country of origin is missing in product data (product_country is empty)")
        
        for epic_attr in epic_attributes:
            if epic_attr.get("isRequired", False):
                attr_code = epic_attr.get("code", "")
                existing_attr = next((attr for attr in result if attr.get("paramcode") == attr_code), None)
                
                if not existing_attr or not existing_attr.get("value"):
                    attr_name = self._get_attr_name_ua(epic_attr)
                    logging.warning(
                        f"Required attribute {attr_code} ({attr_name}) is not filled; "
                        f"using fallback"
                    )
                    filled_attr = self._fill_attribute_fallback(epic_attr, filled_values)
                    if filled_attr and filled_attr.get("value"):
                        result = [attr for attr in result if attr.get("paramcode") != attr_code]
                        result.append(filled_attr)
        
        logging.info(f"Filled {len([a for a in result if a.get('value')])} attributes out of {len(epic_attributes)}")
        return result
    
    def _find_param_in_input(self,
                            epic_attr: Dict[str, Any],
                            product_params: Dict[str, str]) -> Optional[Dict[str, str]]:
        # ""Find a parameter in the input file by attribute name.""
        attr_name_ua = self._get_attr_name_ua(epic_attr)
        attr_name_ru = self._get_attr_name_ru(epic_attr)
        
        for param_name, param_value in product_params.items():
            param_name_lower = param_name.lower().strip()
            
            if (param_name_lower == attr_name_ua.lower().strip() or
                param_name_lower == attr_name_ru.lower().strip()):
                return {"name": param_name, "value": param_value}
            
            if self._is_similar_name(param_name_lower, attr_name_ua, attr_name_ru):
                return {"name": param_name, "value": param_value}
        
        return None
    
    def _fill_attribute_from_input(self,
                                  epic_attr: Dict[str, Any],
                                  matched_param: Dict[str, str],
                                  filled_values: Dict[str, str]) -> Optional[Dict[str, Any]]:
        # ""Fill an attribute from an input-file value.""
        attr_code = epic_attr.get("code", "")
        attr_type = epic_attr.get("type", "")
        param_value = matched_param["value"]
        
        attr_result = self._create_base_attr_result(epic_attr)
        
        if attr_type in ("float", "integer"):
            normalized_value = self.unit_converter.normalize_numeric_value(
                param_value, attr_type, self._get_attr_name_ua(epic_attr)
            )
            if normalized_value is not None:
                attr_result["value"] = str(normalized_value)
                filled_values[attr_code] = str(normalized_value)
                return attr_result
        
        if attr_type in ("select", "multiselect") and "values" in epic_attr:
            values_dict = epic_attr["values"]
            
            exact_match = self.value_matcher.find_exact_match(param_value, values_dict)
            if exact_match:
                code, text, score = exact_match
                attr_result["valuecode"] = code
                attr_result["value"] = text
                filled_values[attr_code] = text
                return attr_result
            
            semantic_match = self.value_matcher.find_semantic_match(
                param_value, values_dict, threshold=0.9
            )
            if semantic_match:
                code, text, score = semantic_match
                attr_result["valuecode"] = code
                attr_result["value"] = text
                filled_values[attr_code] = text
                return attr_result
            
            best_match = self.value_matcher.find_best_match(param_value, values_dict)
            if best_match:
                code, text, score = best_match
                attr_result["valuecode"] = code
                attr_result["value"] = text
                filled_values[attr_code] = text
                logging.warning(f"Used fallback value for attribute {attr_code}: {text} (score: {score:.3f})")
                return attr_result
        
        attr_result["value"] = param_value
        filled_values[attr_code] = param_value
        return attr_result
    
    def _fill_attribute_from_suggestion(self,
                                       epic_attr: Dict[str, Any],
                                       suggested_value: str,
                                       filled_values: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Fill an attribute based on a ChatGPT suggestion.
        Uses semantic dictionary lookup for any attribute type that has a dictionary.
        """
        attr_code = epic_attr.get("code", "")
        attr_type = epic_attr.get("type", "")
        attr_name = self._get_attr_name_ua(epic_attr)
        
        attr_result = self._create_base_attr_result(epic_attr)
        
        if "values" in epic_attr:
            match = self._try_find_in_dictionary(epic_attr, suggested_value)
            if match:
                code, text, score = match
                if attr_type in ("select", "multiselect"):
                    attr_result["valuecode"] = code
                attr_result["value"] = text
                filled_values[attr_code] = text
                logging.info(
                    f"Dictionary value found for attribute {attr_code} ({attr_name}): {text} (score: {score:.3f})"
                )
                return attr_result
        
        if attr_type in ("float", "integer"):
            normalized_value = self.unit_converter.normalize_numeric_value(
                suggested_value, attr_type, attr_name
            )
            if normalized_value is not None:
                attr_result["value"] = str(normalized_value)
                filled_values[attr_code] = str(normalized_value)
                logging.info(f"Used normalized value for numeric attribute {attr_code}: {normalized_value}")
                return attr_result
        
        if attr_type in ("select", "multiselect") and "values" in epic_attr:
            values_dict = epic_attr["values"]
            if values_dict:
                best_match = self.value_matcher.find_best_match(suggested_value, values_dict)
                if best_match:
                    code, text, score = best_match
                    attr_result["valuecode"] = code
                    attr_result["value"] = text
                    filled_values[attr_code] = text
                    logging.warning(
                        f"Used best-matching value for attribute {attr_code}: {text} (score: {score:.3f})"
                    )
                    return attr_result
        
        attr_result["value"] = suggested_value
        filled_values[attr_code] = suggested_value
        logging.info(f"Used suggested value for attribute {attr_code}: {suggested_value}")
        return attr_result
    
    def _try_find_in_dictionary(self,
                                epic_attr: Dict[str, Any],
                                search_value: str) -> Optional[Tuple[str, str, float]]:
        """
        Generic dictionary value lookup with semantic matching.
        
        Args:
            epic_attr: Epicentr attribute object.
            search_value: Value to look up.
            
        Returns:
            Tuple (option_code, value_text, similarity_score) or None.
        """
        if not search_value or "values" not in epic_attr:
            return None
        
        values_dict = epic_attr["values"]
        if not values_dict:
            return None
        
        exact_match = self.value_matcher.find_exact_match(search_value, values_dict)
        if exact_match:
            return exact_match
        
        semantic_match = self.value_matcher.find_semantic_match(
            search_value, values_dict, threshold=0.9
        )
        if semantic_match:
            return semantic_match
        
        best_match = self.value_matcher.find_best_match(search_value, values_dict)
        return best_match
    
    def _fill_attribute_fallback(self,
                                epic_attr: Dict[str, Any],
                                filled_values: Dict[str, str],
                                suggested_value: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fallback attribute fill when a suggestion is missing or cannot be applied.
        
        Args:
            epic_attr: Epicentr attribute object.
            filled_values: Already filled values map.
            suggested_value: Optional suggested value for dictionary lookup.
        """
        attr_code = epic_attr.get("code", "")
        attr_type = epic_attr.get("type", "")
        attr_name = self._get_attr_name_ua(epic_attr)
        
        attr_result = self._create_base_attr_result(epic_attr)
        
        if suggested_value and "values" in epic_attr:
            match = self._try_find_in_dictionary(epic_attr, suggested_value)
            if match:
                code, text, score = match
                attr_result["valuecode"] = code
                attr_result["value"] = text
                filled_values[attr_code] = text
                logging.info(
                    f"Dictionary value found for attribute {attr_code} ({attr_name}): {text} (score: {score:.3f})"
                )
                return attr_result
        
        if attr_type in ("select", "multiselect") and "values" in epic_attr:
            values_dict = epic_attr["values"]
            if values_dict:
                if suggested_value:
                    match = self._try_find_in_dictionary(epic_attr, suggested_value)
                    if match:
                        code, text, score = match
                        attr_result["valuecode"] = code
                        attr_result["value"] = text
                        filled_values[attr_code] = text
                        logging.info(f"Value found via semantic search: {text} (score: {score:.3f})")
                        return attr_result
                
                first_code = list(values_dict.keys())[0]
                first_value = values_dict[first_code]
                attr_result["valuecode"] = first_code
                attr_result["value"] = first_value
                filled_values[attr_code] = first_value
                logging.warning(f"Used first dictionary value for attribute {attr_code}: {first_value}")
                return attr_result
        
        if attr_type in ("text", "string", "textarea") and "values" in epic_attr:
            if suggested_value:
                match = self._try_find_in_dictionary(epic_attr, suggested_value)
                if match:
                    code, text, score = match
                    attr_result["valuecode"] = code
                    attr_result["value"] = text
                    filled_values[attr_code] = text
                    logging.info(f"Text value found in dictionary: {text} (score: {score:.3f})")
                    return attr_result
            
            if suggested_value:
                attr_result["value"] = suggested_value
                filled_values[attr_code] = suggested_value
                logging.warning(f"Used suggested value for text attribute {attr_code}: {suggested_value}")
                return attr_result
        
        if attr_type in ("float", "integer") and "values" in epic_attr:
            if suggested_value:
                match = self._try_find_in_dictionary(epic_attr, suggested_value)
                if match:
                    code, text, score = match
                    attr_result["valuecode"] = code
                    attr_result["value"] = text
                    filled_values[attr_code] = text
                    logging.info(f"Numeric value found in dictionary: {text} (score: {score:.3f})")
                    return attr_result
            
            if suggested_value:
                normalized_value = self.unit_converter.normalize_numeric_value(
                    suggested_value, attr_type, attr_name
                )
                if normalized_value is not None:
                    attr_result["value"] = str(normalized_value)
                    filled_values[attr_code] = str(normalized_value)
                    logging.warning(f"Used normalized value for numeric attribute {attr_code}: {normalized_value}")
                    return attr_result
        
        if suggested_value:
            attr_result["value"] = suggested_value
            filled_values[attr_code] = suggested_value
            logging.warning(f"Used suggested default value for attribute {attr_code}: {suggested_value}")
            return attr_result
        
        if attr_type in ("select", "multiselect") and "values" in epic_attr:
            values_dict = epic_attr.get("values", {})
            if values_dict:
                first_code = list(values_dict.keys())[0]
                first_value = values_dict[first_code]
                attr_result["valuecode"] = first_code
                attr_result["value"] = first_value
                filled_values[attr_code] = first_value
                logging.warning(f"Used first dictionary value (final fallback) for attribute {attr_code}: {first_value}")
                return attr_result
        
        if attr_type in ("text", "string", "textarea"):
            default_value = "Не вказано"
            attr_result["value"] = default_value
            filled_values[attr_code] = default_value
            logging.warning(f"Used default value for text attribute {attr_code}: {default_value}")
            return attr_result
        elif attr_type in ("float", "integer"):
            default_value = "0"
            attr_result["value"] = default_value
            filled_values[attr_code] = default_value
            logging.warning(f"Used default value for numeric attribute {attr_code}: {default_value}")
            return attr_result
        
        logging.error(f"Failed to fill required attribute {attr_code} ({attr_name}, type: {attr_type}); returning an empty attribute")
        return attr_result
    
    def _fill_brand_attribute(self,
                              brand_attr: Dict[str, Any],
                              suggested_brand: str,
                              filled_values: Dict[str, str]) -> Optional[Dict[str, Any]]:
        # ""Fill the brand attribute.""
        attr_result = self._create_base_attr_result(brand_attr)
        attr_result["value"] = suggested_brand
        
        if "values" in brand_attr:
            values_dict = brand_attr["values"]
            
            exact_match = self.value_matcher.find_exact_match(suggested_brand, values_dict)
            if exact_match:
                code, text, score = exact_match
                attr_result["valuecode"] = code
                attr_result["value"] = text
            
            if not attr_result.get("valuecode"):
                semantic_match = self.value_matcher.find_semantic_match(
                    suggested_brand, values_dict, threshold=0.9
                )
                if semantic_match:
                    code, text, score = semantic_match
                    attr_result["valuecode"] = code
                    attr_result["value"] = text
            
            if not attr_result.get("valuecode"):
                best_match = self.value_matcher.find_best_match(suggested_brand, values_dict)
                if best_match:
                    code, text, score = best_match
                    attr_result["valuecode"] = code
                    attr_result["value"] = text
                    logging.warning(f"Used best_match for brand: {text} (code: {code}, score: {score:.3f})")
        else:
            logging.warning(f"Brand '{suggested_brand}' is not in dictionary; using it without code")
        
        filled_values["brand"] = attr_result["value"]
        return attr_result
    
    def _fill_country_attribute(self,
                                country_attr: Dict[str, Any],
                                country_value: str,
                                filled_values: Dict[str, str]) -> Optional[Dict[str, Any]]:
        # ""Fill the country-of-origin attribute.""
        attr_result = self._create_base_attr_result(country_attr)
        attr_result["value"] = country_value
        
        country_code = None
        country_name_normalized = country_value.lower().strip()
        
        if country_name_normalized in self.countries_dict:
            country_code = self.countries_dict[country_name_normalized]
            logging.info(f"Found country code in country_of_origin.json: {country_value} -> {country_code}")
        else:
            for name, code in self.countries_dict.items():
                if name.lower() == country_name_normalized:
                    country_code = code
                    logging.info(f"Found country code in country_of_origin.json (exact match): {country_value} -> {country_code}")
                    break
        
        if country_code:
            attr_result["valuecode"] = country_code
            attr_result["value"] = country_value
        else:
            if "values" in country_attr:
                values_dict = country_attr["values"]
                
                exact_match = self.value_matcher.find_exact_match(country_value, values_dict)
                if exact_match:
                    code, text, score = exact_match
                    attr_result["valuecode"] = code
                    attr_result["value"] = text
                    logging.info(f"Found country code in attribute dictionary (exact match): {country_value} -> {code}")
                
                if not attr_result.get("valuecode"):
                    semantic_match = self.value_matcher.find_semantic_match(
                        country_value, values_dict, threshold=0.9
                    )
                    if semantic_match:
                        code, text, score = semantic_match
                        attr_result["valuecode"] = code
                        attr_result["value"] = text
                        logging.info(f"Found country code in attribute dictionary (semantic search): {country_value} -> {code} (score: {score:.3f})")
                
                if not attr_result.get("valuecode"):
                    best_match = self.value_matcher.find_best_match(country_value, values_dict)
                    if best_match:
                        code, text, score = best_match
                        attr_result["valuecode"] = code
                        attr_result["value"] = text
                        logging.warning(f"Used best-matching country value from attribute dictionary: {country_value} -> {code} (score: {score:.3f})")
            else:
                logging.warning(f"Could not find country code for '{country_value}' - attribute dictionary is empty")
        
        if not attr_result.get("valuecode"):
            if country_name_normalized in ["китай", "china"]:
                attr_result["valuecode"] = "chn"
                logging.warning(f"Used fallback country code 'chn' for: {country_value}")
            else:
                logging.error(f"CRITICAL: Could not find country code for '{country_value}' in country_of_origin.json or attribute dictionary")
        
        filled_values["country_of_origin"] = attr_result["value"]
        return attr_result
    
    def _create_base_attr_result(self, epic_attr: Dict[str, Any]) -> Dict[str, Any]:
        # ""Create base result structure for an attribute.""
        attr_code = epic_attr.get("code", "")
        attr_type = epic_attr.get("type", "")
        is_required = epic_attr.get("isRequired", False)
        attr_name_ua = self._get_attr_name_ua(epic_attr)
        
        return {
            "name": attr_name_ua,
            "paramcode": attr_code,
            "type": attr_type,
            "is_required": is_required,
            "valuecode": None,
            "value": None
        }
    
    def _create_empty_attr_result(self, epic_attr: Dict[str, Any]) -> Dict[str, Any]:
        # ""Create an empty attribute result structure.""
        return self._create_base_attr_result(epic_attr)
    
    def _get_attr_name_ua(self, epic_attr: Dict[str, Any]) -> str:
        # ""Extract the attribute name in Ukrainian.""
        translations = epic_attr.get("translations", [])
        for trans in translations:
            if trans.get("languageCode") == "ua":
                return trans.get("title", "")
        for trans in translations:
            if trans.get("languageCode") == "ru":
                return trans.get("title", "")
        return epic_attr.get("code", "")
    
    def _get_attr_name_ru(self, epic_attr: Dict[str, Any]) -> str:
        # ""Extract the attribute name in Russian.""
        translations = epic_attr.get("translations", [])
        for trans in translations:
            if trans.get("languageCode") == "ru":
                return trans.get("title", "")
        return ""
    
    def _is_similar_name(self, param_name: str, attr_name_ua: str, attr_name_ru: str) -> bool:
        # ""Check whether parameter and attribute names are similar.""
        ua_keywords = set(attr_name_ua.lower().split())
        ru_keywords = set(attr_name_ru.lower().split())
        param_words = set(param_name.split())
        
        common_ua = param_words.intersection(ua_keywords)
        common_ru = param_words.intersection(ru_keywords)
        
        significant_words_ua = {w for w in common_ua if len(w) > 3}
        significant_words_ru = {w for w in common_ru if len(w) > 3}
        
        return len(significant_words_ua) > 0 or len(significant_words_ru) > 0




