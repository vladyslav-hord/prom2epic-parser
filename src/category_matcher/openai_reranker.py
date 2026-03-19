# Candidate reranking with OpenAI embeddings.

import os
import numpy as np
from typing import List, Tuple, Dict, Optional
import logging
import time

try:
    import openai
except ImportError:
    raise ImportError("Install openai first: pip install openai")


class OpenAIReranker:
    # Rerank category candidates using OpenAI embeddings.
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-large"):
        # Initialize the reranker and OpenAI client.
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set OPENAI_API_KEY or pass api_key.")
        
        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key)
        
        self.max_retries = 3
        self.retry_delay = 1.0
        
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Return embeddings for input texts with retry handling.
        if not texts:
            return []
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=texts
                )
                
                embeddings = []
                for item in response.data:
                    embeddings.append(item.embedding)
                
                return embeddings
                
            except openai.RateLimitError:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logging.warning(f"Rate limit reached, waiting {wait_time:.1f}s.")
                    time.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logging.warning(f"Embedding request failed (attempt {attempt + 1}): {e}")
                    time.sleep(self.retry_delay)
                else:
                    raise
        
        return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        # Compute cosine similarity for two vectors.
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def rerank(self, 
               product_context: str, 
               candidates: List[Tuple[str, str, float]], 
               top_k: int = 10) -> List[Tuple[str, str, float]]:
        # Rerank candidates by semantic similarity to product context.
        if not candidates:
            return []

        try:
            texts_to_embed = [product_context]
            for _, cat_name, _ in candidates:
                texts_to_embed.append(cat_name)

            logging.info(f"Requesting OpenAI embeddings for {len(texts_to_embed)} texts.")
            embeddings = self._get_embeddings(texts_to_embed)

            if not embeddings or len(embeddings) != len(texts_to_embed):
                logging.error("Could not fetch embeddings, returning original ranking.")
                return candidates[:top_k]

            product_embedding = embeddings[0]
            category_embeddings = embeddings[1:]

            reranked_candidates = []
            for i, (cat_id, cat_name, local_score) in enumerate(candidates):
                if i < len(category_embeddings):
                    openai_score = self._cosine_similarity(product_embedding, category_embeddings[i])
                    reranked_candidates.append((cat_id, cat_name, openai_score))
                else:
                    reranked_candidates.append((cat_id, cat_name, local_score))

            reranked_candidates.sort(key=lambda x: x[2], reverse=True)

            logging.info(f"OpenAI reranking finished, returning top-{top_k}.")
            return reranked_candidates[:top_k]

        except Exception as e:
            logging.error(f"OpenAI reranking failed: {e}")
            return candidates[:top_k]
    
    def get_embedding_info(self) -> Dict:
        # Return metadata about the embedding model.
        return {
            "model": self.model,
            "provider": "OpenAI",
            "dimension": 3072 if "large" in self.model else 1536,
        }
    
    def estimate_cost(self, num_texts: int) -> float:
        # Estimate embedding cost in USD for a rough workload.
        if "3-large" in self.model:
            cost_per_1k_tokens = 0.00013
        elif "3-small" in self.model:
            cost_per_1k_tokens = 0.00002
        else:
            cost_per_1k_tokens = 0.0001

        estimated_tokens = num_texts * 200
        estimated_cost = (estimated_tokens / 1000) * cost_per_1k_tokens

        return estimated_cost
