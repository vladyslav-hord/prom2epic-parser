# ""Client for Epicentr v2 API.""

import os
import time
import logging
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class EpicAPIClient:
    # ""HTTP client for Epicentr v2 API operations.""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.epicentrm.com.ua/v2/pim"):
        # ""Initialize API client session and retry strategy.""
        self.api_key = api_key or os.getenv('EPIC_API_KEY')
        if not self.api_key:
            raise ValueError("Epicentr API key was not found. Set EPIC_API_KEY or pass api_key explicitly.")
        
        self.base_url = base_url.rstrip('/')
        
        # Configure session-level retry policy.
        self.session = requests.Session()
        retry_strategy = Retry(
            total=10,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Default headers for all requests.
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })
        
        logging.info("EpicAPIClient initialized")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        # ""Execute HTTP request with retry logic.""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = self.session.request(method, url, timeout=30, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                attempt += 1
                if attempt >= max_attempts:
                    logging.error(f"Request failed after {max_attempts} attempts: {e}")
                    raise
                
                wait_time = min(2 ** attempt, 60)
                logging.warning(f"Attempt {attempt}/{max_attempts} failed. Retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
        
        raise requests.RequestException(f"Request failed after {max_attempts} attempts")
    
    def get_attribute_options(self, 
                             attribute_set_code: str, 
                             attribute_code: str, 
                             page: int = 1) -> Dict[str, Any]:
        # ""Get paginated attribute options.""
        endpoint = f"attribute-sets/{attribute_set_code}/attributes/{attribute_code}/options"
        params = {"page": page}
        
        response = self._make_request("GET", endpoint, params=params)
        return response.json()
    
    def get_all_attribute_options(self, 
                                  attribute_set_code: str, 
                                  attribute_code: str,
                                  max_workers: int = 10) -> List[Dict[str, Any]]:
        # ""Get all attribute options with parallel page loading.""
        try:
            first_page_data = self.get_attribute_options(attribute_set_code, attribute_code, 1)
        except requests.RequestException as e:
            logging.error(f"Failed to load first page for attribute {attribute_code}: {e}")
            raise
        
        if isinstance(first_page_data, list):
            logging.info(f"Loaded {len(first_page_data)} values for attribute {attribute_code} (non-paginated)")
            return first_page_data
        
        elif isinstance(first_page_data, dict):
            if "items" not in first_page_data:
                logging.warning(f"Unexpected response format for attribute {attribute_code}: {first_page_data}")
                return []
            
            total_pages = first_page_data.get("pages", 1)
            first_page_items = first_page_data.get("items", [])
            
            if total_pages == 1:
                logging.info(f"Loaded {len(first_page_items)} values for attribute {attribute_code}")
                return first_page_items
            
            logging.info(f"Loading {total_pages} pages for attribute {attribute_code} in parallel (up to {max_workers} workers)")
            
            all_items = list(first_page_items)
            
            def load_page(page_num: int) -> List[Dict[str, Any]]:
                # ""Load a single page.""
                try:
                    response_data = self.get_attribute_options(attribute_set_code, attribute_code, page_num)
                    if isinstance(response_data, dict) and "items" in response_data:
                        return response_data["items"]
                    elif isinstance(response_data, list):
                        return response_data
                    return []
                except Exception as e:
                    logging.error(f"Failed to load page {page_num} for attribute {attribute_code}: {e}")
                    return []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_page = {
                    executor.submit(load_page, page): page 
                    for page in range(2, total_pages + 1)
                }
                
                completed = 0
                for future in as_completed(future_to_page):
                    page_num = future_to_page[future]
                    try:
                        items = future.result()
                        all_items.extend(items)
                        completed += 1
                        
                        if completed % 10 == 0 or completed == total_pages - 1:
                            logging.info(f"Loaded {completed + 1}/{total_pages} pages for attribute {attribute_code}")
                    except Exception as e:
                        logging.error(f"Failed processing result of page {page_num} for attribute {attribute_code}: {e}")
            
            logging.info(f"Loaded {len(all_items)} values for attribute {attribute_code} across {total_pages} pages")
            return all_items
        
        else:
            logging.warning(f"Unknown response format for attribute {attribute_code}")
            return []
    
    def extract_option_value(self, option_item: Dict[str, Any]) -> str:
        # ""Extract option value with UA -> RU fallback priority.""
        if "translations" in option_item:
            for translation in option_item["translations"]:
                if translation.get("languageCode") == "ua":
                    return translation.get("value", "")
                if translation.get("languageCode") == "ru":
                    return translation.get("value", "")
        
        return option_item.get("value") or option_item.get("name") or option_item.get("code", "")

