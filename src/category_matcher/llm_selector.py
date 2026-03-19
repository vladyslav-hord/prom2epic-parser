# Final category selection using an LLM.

import os
import json
from typing import List, Tuple, Dict, Optional
import logging
import time

try:
    import openai
except ImportError:
    raise ImportError("Install openai first: pip install openai")


class LLMSelector:
    # Select the best category from candidate list via OpenAI.
    
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 model: str = "gpt-4o-mini",
                 temperature: float = 0.1):
        # Initialize selector settings and OpenAI client.
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set OPENAI_API_KEY or pass api_key.")
        
        self.model = model
        self.temperature = temperature
        self.client = openai.OpenAI(api_key=self.api_key)
        
        self.max_retries = 3
        self.retry_delay = 1.0
    
    def _create_selection_prompt(self, 
                               product_context: str, 
                               candidates: List[Tuple[str, str, float]]) -> str:
        # Build the prompt for category selection.
        candidates_text = ""
        for i, (cat_id, cat_name, score) in enumerate(candidates, 1):
            candidates_text += f"{i}. [{cat_id}] {cat_name} (relevance: {score:.3f})\n"
        
        prompt = f"""You are a product classification expert for Epic, a Ukrainian marketplace.

PRODUCT:
{product_context}

TASK: Choose the BEST category from the candidates below. Priority is to ACCEPT a fitting category instead of rejecting the product.

CANDIDATES:
{candidates_text}

SELECTION CRITERIA:
1. The category must describe the product (it may be broad but still relevant).
2. If multiple categories fit, choose the most specific one.
3. If a category describes the product even broadly, ACCEPT it.
4. Reject only when categories clearly do not fit or contradict the product.
5. Consider technical specifics only when they are critical (wireless vs wired, phone vs laptop use case).

REASONING STEPS:
Step 1: Identify product type.
Step 2: Identify the main function.
Step 3: Compare all candidates and keep those that describe the product.
Step 4: Pick the most specific suitable category (or broader one if needed).
Step 5: If at least one category fits, ACCEPT it, even if not perfect.
Step 6: Estimate confidence (0-100%).

RESPONSE FORMAT (strict JSON):
{{
  "reasoning": "Step-by-step reasoning",
  "selected_category_id": "Category ID or null if rejected",
  "selected_category_name": "Category name or null",
  "confidence": number from 0 to 100,
  "rejected": true/false
}}

IMPORTANT:
- Accept a category if it describes the product, even with 40-50% confidence.
- Reject only when categories clearly do not match (typically confidence < 30%) or contradict the product.
- Priority: accept a suitable category instead of rejecting."""

        return prompt
    
    def _parse_llm_response(self, response_text: str) -> Dict:
        # Parse and validate LLM JSON response.
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                
                required_fields = ['selected_category_id', 'confidence', 'rejected']
                for field in required_fields:
                    if field not in result:
                        raise ValueError(f"Missing required field: {field}")

                if result['rejected']:
                    result['selected_category_id'] = None
                    result['selected_category_name'] = None
                
                return result
            else:
                raise ValueError("JSON payload not found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Failed to parse LLM response: {e}")
            logging.error(f"LLM response text: {response_text}")

            return {
                "reasoning": f"Response parsing failed: {e}",
                "selected_category_id": None,
                "selected_category_name": None,
                "confidence": 0,
                "rejected": True
            }
    
    def select_category(self, 
                       product_context: str, 
                       candidates: List[Tuple[str, str, float]]) -> Dict:
        # Select a final category from reranked candidates.
        if not candidates:
            return {
                "reasoning": "No candidates available for selection",
                "selected_category_id": None,
                "selected_category_name": None,
                "confidence": 0,
                "rejected": True
            }
        
        prompt = self._create_selection_prompt(product_context, candidates)
        
        for attempt in range(self.max_retries):
            try:
                logging.info(f"Sending request to LLM (attempt {attempt + 1})...")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a product classification expert. Respond in strict JSON."
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    temperature=self.temperature,
                    max_tokens=1000
                )
                
                response_text = response.choices[0].message.content
                result = self._parse_llm_response(response_text)
                
                logging.info(
                    f"LLM selection done. Rejected: {result['rejected']}, "
                    f"confidence: {result['confidence']}%"
                )
                
                return result
                
            except openai.RateLimitError:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logging.warning(f"Rate limit reached, waiting {wait_time:.1f}s.")
                    time.sleep(wait_time)
                else:
                    logging.error("Rate limit retry budget exhausted.")
                    break
                    
            except Exception as e:
                logging.error(f"LLM call failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    break

        return {
            "reasoning": "LLM request failed",
            "selected_category_id": None,
            "selected_category_name": None,
            "confidence": 0,
            "rejected": True
        }
    
    def suggest_categories(self,
                          product_context: str,
                          rejection_reason: str,
                          rejected_candidates: Optional[List[Tuple[str, str, float]]] = None) -> List[str]:
        # Ask LLM for alternative category names after rejection.
        prompt = self._create_suggestion_prompt(product_context, rejection_reason, rejected_candidates)
        
        for attempt in range(self.max_retries):
            try:
                logging.info(f"Requesting category suggestions from ChatGPT (attempt {attempt + 1})...")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert in product classification for Epic, "
                                "a Ukrainian marketplace. Respond in strict JSON."
                            )
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=self.temperature,
                    max_tokens=500,
                    response_format={"type": "json_object"}
                )
                
                response_text = response.choices[0].message.content
                result = json.loads(response_text)
                
                suggested_categories = result.get("suggested_categories", [])
                
                if not suggested_categories:
                    logging.warning("ChatGPT did not suggest categories.")
                    return []

                suggested_categories = [cat.strip() for cat in suggested_categories if cat and cat.strip()]

                logging.info(
                    f"ChatGPT suggested {len(suggested_categories)} categories: "
                    f"{', '.join(suggested_categories[:3])}..."
                )
                return suggested_categories
                
            except openai.RateLimitError:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logging.warning(f"Rate limit reached, waiting {wait_time:.1f}s.")
                    time.sleep(wait_time)
                else:
                    logging.error("Rate limit retry budget exhausted.")
                    break
                    
            except Exception as e:
                logging.error(f"Suggestion request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    break

        logging.error("Failed to get category suggestions from ChatGPT.")
        return []
    
    def _create_suggestion_prompt(self,
                                 product_context: str,
                                 rejection_reason: str,
                                 rejected_candidates: Optional[List[Tuple[str, str, float]]] = None) -> str:
        # Build prompt to request fallback category suggestions.
        candidates_text = ""
        if rejected_candidates:
            candidates_text = "\nREJECTED CANDIDATES (not suitable):\n"
            for i, (cat_id, cat_name, score) in enumerate(rejected_candidates[:10], 1):
                candidates_text += f"{i}. [{cat_id}] {cat_name} (relevance: {score:.3f})\n"
        
        prompt = f"""You are a product classification expert for Epic, a Ukrainian marketplace.

PRODUCT:
{product_context}

SITUATION: The product was rejected because the proposed categories did not fit.
REJECTION REASON: {rejection_reason}
{candidates_text}

TASK: Suggest 3-5 most suitable categories based on product description.

IMPORTANT:
1. Category names must be in Ukrainian.
2. Categories must describe the product accurately.
3. Prefer specific categories over generic ones.
4. Consider important product specifics (material, purpose, device type, etc.).

RESPONSE FORMAT (strict JSON):
{{
  "suggested_categories": [
    "Category name 1",
    "Category name 2",
    "Category name 3"
  ],
  "reasoning": "Short explanation of why these categories fit"
}}

EXAMPLE:
{{
  "suggested_categories": [
    "Дверні ручки",
    "Фурнітура для дверей",
    "Меблева фурнітура"
  ],
  "reasoning": "This is a door handle, so door hardware categories are a good fit"
}}

RESPONSE (JSON only, no extra text):"""
        
        return prompt
    
    def estimate_cost(self, num_requests: int, avg_tokens_per_request: int = 800) -> float:
        # Estimate LLM request cost in USD.
        if "gpt-4" in self.model.lower():
            if "turbo" in self.model.lower() or "mini" in self.model.lower():
                input_cost_per_1k = 0.00015
                output_cost_per_1k = 0.0006
            else:
                input_cost_per_1k = 0.01
                output_cost_per_1k = 0.03
        else:
            input_cost_per_1k = 0.0015
            output_cost_per_1k = 0.002
        
        total_input_tokens = num_requests * avg_tokens_per_request
        total_output_tokens = num_requests * 200
        
        input_cost = (total_input_tokens / 1000) * input_cost_per_1k
        output_cost = (total_output_tokens / 1000) * output_cost_per_1k
        
        return input_cost + output_cost
    
    def get_model_info(self) -> Dict:
        # Return selector configuration metadata.
        return {
            "model": self.model,
            "temperature": self.temperature,
            "provider": "OpenAI",
            "max_retries": self.max_retries
        }
