# Epic category hierarchy helpers.

import json
from typing import Dict, List, Tuple, Optional, Union
from pathlib import Path


class HierarchyManager:
    # Manage hierarchy loading, traversal, and weighting.
    
    def __init__(self, hierarchy_file: str = "data/other/epic_categories_hierarchical.json"):
        # Initialize hierarchy data and flattened lookup tables.
        self.hierarchy_file = Path(hierarchy_file)
        self.hierarchy_data = self._load_hierarchy()
        self.flat_categories = self._extract_flat_categories()
        self.super_categories = self._extract_super_categories()
        
    def _load_hierarchy(self) -> Dict:
        # Load hierarchy JSON from disk.
        try:
            with open(self.hierarchy_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Hierarchy file not found: {self.hierarchy_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid hierarchy JSON: {e}")
    
    def _extract_flat_categories(self) -> Dict[str, Dict]:
        # Build a flat category map with metadata.
        categories = {}
        
        def extract_recursive(node, path=[]):
            if 'categories' in node and node['categories']:
                for category in node['categories']:
                    cat_id = category['id']
                    categories[cat_id] = {
                        'id': cat_id,
                        'name': category['name'],
                        'path': category.get('path', path),
                        'level': len(category.get('path', path))
                    }
            
            if 'children' in node:
                for child_name, child_node in node['children'].items():
                    new_path = path + [child_name]
                    extract_recursive(child_node, new_path)
        
        if 'hierarchy' in self.hierarchy_data:
            for root_name, root_node in self.hierarchy_data['hierarchy'].items():
                extract_recursive(root_node, [root_name])
        
        return categories
    
    def _extract_super_categories(self) -> List[str]:
        # Return root-level category names.
        if 'hierarchy' in self.hierarchy_data:
            return list(self.hierarchy_data['hierarchy'].keys())
        return []
    
    def get_category_by_id(self, category_id: str) -> Optional[Dict]:
        # Get category metadata by ID.
        return self.flat_categories.get(category_id)
    
    def get_categories_by_super_category(self, super_category: str) -> List[Dict]:
        # Get categories that belong to a given root branch.
        categories = []
        for cat_id, cat_info in self.flat_categories.items():
            if cat_info['path'] and cat_info['path'][0] == super_category:
                categories.append(cat_info)
        return categories
    
    def calculate_super_category_probabilities(self, product_context: str) -> Dict[str, float]:
        # Estimate root-branch probabilities from product context.
        context_lower = product_context.lower()
        probabilities = {}

        super_category_keywords = {
            "Автотовари": ["авто", "машин", "автомобил", "car", "auto"],
            "Електроніка": ["электрон", "телефон", "компьютер", "зарядк", "гаджет"],
            "Дім та сад": ["дом", "сад", "мебел", "декор", "кухн"],
            "Одяг та взуття": ["одежд", "обув", "футболк", "джинс", "платт"],
            "Спорт": ["спорт", "фитнес", "тренажер", "мяч", "велосипед"],
            "Краса та здоров'я": ["косметик", "парфюм", "здоров", "витамин", "крем"],
        }
        
        total_matches = 0
        for super_cat, keywords in super_category_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in context_lower)
            probabilities[super_cat] = matches
            total_matches += matches

        if total_matches > 0:
            for super_cat in probabilities:
                probabilities[super_cat] /= total_matches
        else:
            uniform_prob = 1.0 / len(self.super_categories) if self.super_categories else 1.0
            for super_cat in self.super_categories:
                probabilities[super_cat] = uniform_prob

        return probabilities
    
    def validate_hierarchy_consistency(self, candidates: List[Union[Tuple[str, str, float], Tuple[str, float]]]) -> Dict:
        # Evaluate whether candidates are concentrated in one branch.
        if not candidates:
            return {"is_consistent": True, "concentration": 0.0, "dominant_branch": None}

        super_category_counts = {}
        for candidate in candidates:
            cat_id = candidate[0]
            cat_info = self.get_category_by_id(cat_id)
            if cat_info and cat_info['path']:
                super_cat = cat_info['path'][0]
                if super_cat not in super_category_counts:
                    super_category_counts[super_cat] = 0
                super_category_counts[super_cat] += 1
        
        if not super_category_counts:
            return {"is_consistent": True, "concentration": 0.0, "dominant_branch": None}

        dominant_branch = max(super_category_counts.items(), key=lambda x: x[1])
        concentration = dominant_branch[1] / len(candidates)

        return {
            "is_consistent": concentration > 0.7,
            "concentration": concentration,
            "dominant_branch": dominant_branch[0],
            "distribution": super_category_counts
        }
    
    def apply_hierarchy_weights(self, candidates: List[Union[Tuple[str, str, float], Tuple[str, float]]], 
                              super_category_probs: Dict[str, float]) -> List[Union[Tuple[str, str, float], Tuple[str, float]]]:
        # Apply root-branch probability weights to candidate scores.
        weighted_candidates = []

        for candidate in candidates:
            if len(candidate) == 3:
                cat_id, cat_name, score = candidate
            else:
                cat_id, score = candidate
                cat_name = None

            cat_info = self.get_category_by_id(cat_id)
            if cat_info and cat_info['path']:
                super_cat = cat_info['path'][0]
                hierarchy_weight = super_category_probs.get(super_cat, 0.1)
                weighted_score = score * (0.7 + 0.3 * hierarchy_weight)

                if cat_name:
                    weighted_candidates.append((cat_id, cat_name, weighted_score))
                else:
                    weighted_candidates.append((cat_id, weighted_score))
            else:
                weighted_candidates.append(candidate)

        return sorted(weighted_candidates, key=lambda x: x[-1], reverse=True)