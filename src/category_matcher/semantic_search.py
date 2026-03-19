# Semantic category search with local embeddings.

import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import pickle
import logging

try:
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim
except ImportError:
    raise ImportError("Install sentence-transformers first: pip install sentence-transformers")


class SemanticSearcher:
    # Search categories by semantic similarity.
    
    def __init__(self, 
                 categories_file: str = "data/other/epic_categories.json",
                 model_name: str = "intfloat/multilingual-e5-large",
                 cache_dir: str = "data/other"):
        # Initialize model, categories, and cached embeddings.
        self.categories_file = Path(categories_file)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.categories = self._load_categories()

        logging.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name

        logging.info(f"Loading or building embeddings for {len(self.categories)} categories...")
        self.category_embeddings = self._load_or_create_embeddings()
        logging.info(f"Embeddings are ready: {len(self.category_embeddings)} vectors.")
        
    def _load_categories(self) -> Dict[str, str]:
        # Load category ID to name mapping from JSON.
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Categories file not found: {self.categories_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid categories JSON: {e}")
    
    def _get_embeddings_cache_path(self) -> Path:
        # Return embedding cache file path for current dimension.
        model_name_safe = self.model.get_sentence_embedding_dimension()
        return self.cache_dir / f"category_embeddings_{model_name_safe}d.pkl"
    
    def _load_or_create_embeddings(self) -> np.ndarray:
        # Load embeddings from cache, or build and persist them.
        cache_path = self._get_embeddings_cache_path()

        if cache_path.exists():
            logging.info(f"Checking embedding cache: {cache_path}")
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)

                cached_ids = cached_data.get('category_ids', [])
                current_ids = list(self.categories.keys())

                cached_ids_set = {str(cid) for cid in cached_ids}
                current_ids_set = {str(cid) for cid in current_ids}

                cached_count = cached_data.get('categories_count', 0)
                current_count = len(self.categories)
                cached_model_name = cached_data.get('model_name', '')

                model_matches = (cached_model_name == self.model_name) if cached_model_name else True

                if (cached_count == current_count and 
                    cached_ids_set == current_ids_set and
                    model_matches):
                    logging.info(
                        f"Cache is valid. Using embeddings for {current_count} categories "
                        f"(model: {self.model_name})."
                    )
                    return cached_data['embeddings']
                else:
                    if cached_model_name != self.model_name:
                        logging.warning(
                            f"Cache is stale: model changed "
                            f"({cached_model_name} -> {self.model_name})"
                        )
                    elif cached_count != current_count:
                        logging.warning(
                            f"Cache is stale: category count changed "
                            f"({cached_count} -> {current_count})"
                        )
                    else:
                        diff_count = len(cached_ids_set.symmetric_difference(current_ids_set))
                        logging.warning(
                            f"Cache is stale: category IDs changed "
                            f"(difference: {diff_count} categories)"
                        )
                    logging.info("Rebuilding embeddings...")
            except Exception as e:
                logging.warning(f"Failed to load cache: {e}. Rebuilding embeddings.", exc_info=True)

        logging.info(f"Building embeddings for {len(self.categories)} categories...")
        category_texts = list(self.categories.values())
        embeddings = self.model.encode(category_texts, show_progress_bar=True)

        category_ids_normalized = [str(cid) for cid in self.categories.keys()]
        cache_data = {
            'embeddings': embeddings,
            'categories_count': len(self.categories),
            'category_ids': category_ids_normalized,
            'model_dimension': self.model.get_sentence_embedding_dimension(),
            'model_name': self.model_name
        }

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            logging.info(f"Embeddings cached at: {cache_path}")
        except Exception as e:
            logging.warning(f"Failed to save cache: {e}")

        return embeddings
    
    def search(self, query: str, top_k: int = 100) -> List[Tuple[str, str, float]]:
        # Run semantic category search and return top results.
        if not query.strip():
            return []

        query_embedding = self.model.encode([query])

        similarities = cos_sim(query_embedding, self.category_embeddings)[0]

        top_indices = similarities.argsort(descending=True)[:top_k]

        results = []
        category_ids = list(self.categories.keys())

        for idx in top_indices:
            idx_int = int(idx)
            category_id = category_ids[idx_int]
            category_name = self.categories[category_id]
            similarity_score = float(similarities[idx])

            results.append((category_id, category_name, similarity_score))

        return results
    
    def search_categories_by_names(self,
                                  category_names: List[str],
                                  top_k_per_name: int = 3) -> List[Tuple[str, str, float]]:
        # Search category list by suggested names and merge unique matches.
        if not category_names:
            return []

        all_results = []
        seen_category_ids = set()

        for category_name in category_names:
            if not category_name or not category_name.strip():
                continue

            search_results = self.search(category_name.strip(), top_k=top_k_per_name)

            for cat_id, cat_name, score in search_results:
                if cat_id not in seen_category_ids:
                    all_results.append((cat_id, cat_name, score))
                    seen_category_ids.add(cat_id)

        all_results.sort(key=lambda x: x[2], reverse=True)

        logging.info(
            f"Found {len(all_results)} unique categories for {len(category_names)} suggested names."
        )

        return all_results
    
    def prepare_product_context(self, product_data: Dict) -> str:
        # Create a compact product context string for embedding search.
        context_parts = []

        if product_data.get('name_ua'):
            context_parts.append(f"Name (UA): {product_data['name_ua']}")
        if product_data.get('name'):
            context_parts.append(f"Name (RU): {product_data['name']}")

        if product_data.get('description_ua'):
            desc_ua = product_data['description_ua'][:200]
            context_parts.append(f"Description (UA): {desc_ua}")
        if product_data.get('description'):
            desc = product_data['description'][:200]
            context_parts.append(f"Description (RU): {desc}")

        if product_data.get('brand'):
            context_parts.append(f"Brand: {product_data['brand']}")

        if product_data.get('params'):
            important_params = []
            for param_name, param_value in product_data['params'].items():
                if len(param_name) > 2 and len(param_value) > 1:
                    important_params.append(f"{param_name}: {param_value}")

            if important_params:
                context_parts.append("Parameters: " + "; ".join(important_params[:5]))

        if product_data.get('category_name'):
            context_parts.append(f"Source category: {product_data['category_name']}")

        return " | ".join(context_parts)
    
    def get_model_info(self) -> Dict:
        # Return model and cache metadata.
        return {
            "model_name": self.model._modules['0'].auto_model.name_or_path,
            "embedding_dimension": self.model.get_sentence_embedding_dimension(),
            "categories_count": len(self.categories),
            "cache_path": str(self._get_embeddings_cache_path())
        }
