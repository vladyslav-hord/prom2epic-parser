# Main product categorization flow (Scheme B).

import time
import logging
from typing import Dict, Optional, List, Any

from .hierarchy import HierarchyManager
from .semantic_search import SemanticSearcher
from .openai_reranker import OpenAIReranker
from .llm_selector import LLMSelector


class CategoryMatcher:
    # Main orchestrator for product category matching.
    
    def __init__(self, 
                 categories_file: str = "data/other/epic_categories.json",
                 hierarchy_file: str = "data/other/epic_categories_hierarchical.json",
                 openai_api_key: Optional[str] = None,
                 semantic_model: str = "intfloat/multilingual-e5-large",
                 llm_model: str = "gpt-4o-mini",
                 cache_dir: str = "data/other"):
        # Initialize all matching components.
        self.cache_dir = cache_dir

        logging.info("Initializing CategoryMatcher...")
        logging.info(f"Cache directory: {cache_dir}")

        self.hierarchy_manager = HierarchyManager(hierarchy_file)
        logging.info("HierarchyManager initialized.")

        logging.info(f"Creating SemanticSearcher (model: {semantic_model}, cache_dir: {cache_dir})...")
        self.semantic_searcher = SemanticSearcher(
            categories_file=categories_file,
            model_name=semantic_model,
            cache_dir=cache_dir
        )
        logging.info("SemanticSearcher initialized.")

        self.openai_reranker = OpenAIReranker(api_key=openai_api_key)
        logging.info("OpenAIReranker initialized.")

        self.llm_selector = LLMSelector(api_key=openai_api_key, model=llm_model)
        logging.info("LLMSelector initialized.")

        logging.info("CategoryMatcher is ready.")
    
    def classify(self, product_data: Dict, load_attributes: bool = False, enable_retry: bool = True) -> Dict:
        # Classify one product using semantic search + reranking + LLM.
        start_time = time.time()

        logging.info("Scheme B: semantic search with hierarchy weights.")

        product_context = self.semantic_searcher.prepare_product_context(product_data)

        semantic_candidates = self.semantic_searcher.search(product_context, top_k=100)

        super_category_probs = self.hierarchy_manager.calculate_super_category_probabilities(
            product_context
        )

        weighted_candidates = self.hierarchy_manager.apply_hierarchy_weights(
            semantic_candidates, super_category_probs
        )

        logging.info(f"Stage 1: semantic search + hierarchy weights, {len(weighted_candidates)} candidates.")

        openai_candidates = self.openai_reranker.rerank(
            product_context, weighted_candidates, top_k=15
        )

        logging.info(f"Stage 2: OpenAI reranking, top-{len(openai_candidates)} candidates.")

        llm_result = self.llm_selector.select_category(product_context, openai_candidates)

        logging.info(f"Stage 3: LLM selection completed, rejected: {llm_result['rejected']}")

        retry_attempted = False
        suggested_categories = []
        retry_candidates_count = 0
        retry_successful = False

        if llm_result['rejected'] and enable_retry:
            logging.info("Product rejected, starting retry flow...")
            retry_attempted = True

            try:
                suggested_categories = self.llm_selector.suggest_categories(
                    product_context=product_context,
                    rejection_reason=llm_result.get('reasoning', 'No suitable category found'),
                    rejected_candidates=openai_candidates
                )

                if suggested_categories:
                    logging.info(
                        f"ChatGPT suggested {len(suggested_categories)} categories: "
                        f"{', '.join(suggested_categories[:3])}..."
                    )

                    retry_candidates = self.semantic_searcher.search_categories_by_names(
                        suggested_categories,
                        top_k_per_name=3
                    )
                    retry_candidates_count = len(retry_candidates)

                    if retry_candidates:
                        logging.info(f"Found {len(retry_candidates)} categories for retry.")

                        retry_openai_candidates = self.openai_reranker.rerank(
                            product_context, retry_candidates, top_k=min(15, len(retry_candidates))
                        )

                        retry_llm_result = self.llm_selector.select_category(
                            product_context, retry_openai_candidates
                        )

                        if not retry_llm_result['rejected']:
                            logging.info(
                                "Retry succeeded, selected category: "
                                f"{retry_llm_result['selected_category_name']}"
                            )
                            llm_result = retry_llm_result
                            retry_successful = True
                        else:
                            logging.info("Retry did not produce a valid category.")
                    else:
                        logging.warning("No matching categories found for suggested names.")
                else:
                    logging.warning("ChatGPT did not return category suggestions for retry.")

            except Exception as e:
                logging.error(f"Retry flow failed: {e}", exc_info=True)

        processing_time = time.time() - start_time

        result = {
            "product_name": product_data.get('name', ''),
            "original_category": product_data.get('category_name', ''),
            "selected_category": {
                "id": llm_result['selected_category_id'],
                "name": llm_result['selected_category_name']
            } if not llm_result['rejected'] else None,
            "rejected": llm_result['rejected'],
            "confidence": llm_result['confidence'],
            "reasoning": llm_result['reasoning'],
            "processing_time": processing_time,
            "scheme": "B",
            "hierarchy_probs": super_category_probs,
            "candidates_count": {
                "semantic": len(semantic_candidates),
                "weighted": len(weighted_candidates),
                "openai": len(openai_candidates)
            },
            "retry_attempted": retry_attempted,
            "suggested_categories": suggested_categories,
            "retry_candidates_count": retry_candidates_count,
            "retry_successful": retry_successful
        }

        if load_attributes and not llm_result['rejected'] and llm_result.get('selected_category_id'):
            try:
                from ..utils.attributes_loader import AttributesLoader
                attributes_loader = AttributesLoader()
                epic_attributes = attributes_loader.get_category_attributes_with_values(
                    llm_result['selected_category_id'], load_values=True
                )
                result["epic_attributes"] = epic_attributes
                logging.info(
                    f"Loaded {len(epic_attributes)} attributes for "
                    f"category {llm_result['selected_category_id']}."
                )
            except Exception as e:
                logging.error(f"Failed to load attributes: {e}")
                result["epic_attributes"] = []

        return result
    
    
    def get_system_info(self) -> Dict:
        # Return metadata about matcher components.
        return {
            "semantic_model": self.semantic_searcher.get_model_info(),
            "openai_reranker": self.openai_reranker.get_embedding_info(),
            "llm_selector": self.llm_selector.get_model_info(),
            "categories_count": len(self.semantic_searcher.categories),
            "super_categories": self.hierarchy_manager.super_categories
        }
    
    def estimate_costs(self, num_products: int) -> Dict:
        # Estimate processing costs for a product batch.
        embedding_cost = self.openai_reranker.estimate_cost(num_products * 16)

        llm_cost = self.llm_selector.estimate_cost(num_products)

        total_cost = embedding_cost + llm_cost

        return {
            "openai_embeddings": embedding_cost,
            "llm_selection": llm_cost,
            "total": total_cost,
            "cost_per_product": total_cost / num_products if num_products > 0 else 0
        }
