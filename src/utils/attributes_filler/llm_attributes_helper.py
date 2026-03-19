# ""OpenAI helper for attribute value suggestions.""

import os
import json
import logging
from typing import Dict, List, Optional, Any

try:
    import openai
except ImportError:
    raise ImportError("Install openai: pip install openai")


class LLMAttributesHelper:
    # ""Run ChatGPT requests for attribute filling.""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        # ""Initialize OpenAI client and model.""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key was not found. Set OPENAI_API_KEY or pass api_key explicitly.")
        
        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key)
        
        logging.info(f"LLMAttributesHelper initialized with model {model}")
    
    def suggest_attribute_values(self,
                                attributes: List[Dict[str, Any]],
                                product_name_ua: str,
                                product_description_ua: str,
                                product_params: Dict[str, str],
                                category_name: str,
                                existing_values: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        # ""Request suggested values for missing attributes.""
        prompt = self._create_attributes_prompt(
            attributes, product_name_ua, product_description_ua,
            product_params, category_name, existing_values
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in filling product attributes for the Ukrainian Epicentr marketplace. Suggest values for required attributes based on product details."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content
            result = json.loads(response_text)
            
            logging.info(f"ChatGPT suggested values for {len(result)} attributes")
            return result
            
        except Exception as e:
            logging.error(f"ChatGPT request failed: {e}")
            return {}
    
    def _create_attributes_prompt(self,
                                  attributes: List[Dict[str, Any]],
                                  product_name_ua: str,
                                  product_description_ua: str,
                                  product_params: Dict[str, str],
                                  category_name: str,
                                  existing_values: Optional[Dict[str, str]] = None) -> str:
        # ""Build prompt for attribute value suggestion.""
        # Формируем список атрибутов с описанием
        attributes_list = []
        required_attr_codes = []  # Список кодов для проверки полноты ответа
        for attr in attributes:
            attr_code = attr.get("code", "")
            attr_name = attr.get("translations", [{}])[0].get("title", "") if attr.get("translations") else ""
            attr_type = attr.get("type", "")
            is_required = attr.get("isRequired", False)
            
            if not is_required:
                continue
            
            required_attr_codes.append(attr_code)
            attr_desc = f"- {attr_name} (код: {attr_code}, тип: {attr_type})"
            
            # Добавляем информацию о формате ответа
            if attr_type in ("select", "multiselect"):
                attr_desc += " - choose a value from available options"
            elif attr_type in ("float", "integer"):
                if "вага" in attr_name.lower() or "вес" in attr_name.lower():
                    attr_desc += " - provide weight in GRAMS"
                elif any(kw in attr_name.lower() for kw in ["ширина", "высота", "глубина", "длина", "размер"]):
                    attr_desc += " - provide size in MILLIMETERS"
                else:
                    attr_desc += " - provide a numeric value"
            
            attributes_list.append(attr_desc)
        
        attributes_text = "\n".join(attributes_list)
        
        # Формируем пример JSON со всеми кодами атрибутов
        example_json_lines = [f'  "{code}": "value for {code}"' for code in required_attr_codes]
        example_json = "{\n" + ",\n".join(example_json_lines) + "\n}"
        
        # Формируем параметры товара
        params_text = ""
        if product_params:
            params_lines = [f"- {name}: {value}" for name, value in product_params.items()]
            params_text = "\n".join(params_lines)
        else:
            params_text = "No parameters provided"
        
        # Формируем уже заполненные значения
        existing_text = ""
        if existing_values:
            existing_lines = [f"- {attr_code}: {value}" for attr_code, value in existing_values.items()]
            existing_text = "\n".join(existing_lines)
        else:
            existing_text = "No pre-filled values"
        
        prompt = f"""Task: Fill required product attributes for Epicentr import.

PRODUCT:
Name: {product_name_ua}
Category: {category_name}
Description: {product_description_ua[:500] if product_description_ua else "No description provided"}

INPUT FILE PARAMETERS:
{params_text}

ALREADY FILLED VALUES:
{existing_text}

REQUIRED ATTRIBUTES TO FILL:
{attributes_text}

CRITICAL RULES:
1. Every attribute listed above MUST be present in the JSON response.
2. Do not skip attributes even when uncertain; provide the most likely value.
3. All values must be in Ukrainian.
4. For select/multiselect, choose the best matching option by product context.
5. For numeric attributes: weight in grams, dimensions in millimeters.
6. Do not return empty values or null.

JSON RESPONSE FORMAT:
Your JSON must include all these attribute codes:
{', '.join(required_attr_codes)}

Example response:
{example_json}

Reply with JSON only, no extra text."""
        
        return prompt
    
    def suggest_brand(self,
                     product_name_ua: str,
                     product_description_ua: str,
                     product_params: Dict[str, str],
                     category_name: str) -> Optional[str]:
        # ""Request suggested brand for product.""
        prompt = self._create_brand_prompt(
            product_name_ua, product_description_ua, product_params, category_name
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at determining product brands from product data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content
            result = json.loads(response_text)
            
            brand = result.get("brand")
            if brand:
                logging.info(f"ChatGPT suggested brand: {brand}")
                return brand
            
            return None
            
        except Exception as e:
            logging.error(f"Brand suggestion request failed: {e}")
            return None
    
    def _create_brand_prompt(self,
                            product_name_ua: str,
                            product_description_ua: str,
                            product_params: Dict[str, str],
                            category_name: str) -> str:
        # ""Build prompt for brand detection.""
        params_text = ""
        if product_params:
            params_lines = [f"- {name}: {value}" for name, value in product_params.items()]
            params_text = "\n".join(params_lines)
        else:
            params_text = "No parameters provided"
        
        prompt = f"""Task: Determine product brand for Epicentr import.

PRODUCT:
Name: {product_name_ua}
Category: {category_name}
Description: {product_description_ua[:500] if product_description_ua else "No description provided"}

PARAMETERS:
{params_text}

CRITICAL RULES:
1. Brand is required.
2. Return brand in Ukrainian where applicable (keep global brand names unchanged).
3. Never return generic placeholders like "Unknown", "No brand", or empty values.
4. If uncertain, still provide the most likely brand.
5. If no reliable brand is found, return "USE_FALLBACK_SEARCH".

JSON RESPONSE FORMAT:
{{
  "brand": "brand name" or "USE_FALLBACK_SEARCH"
}}

Reply with JSON only, no extra text."""
        
        return prompt




