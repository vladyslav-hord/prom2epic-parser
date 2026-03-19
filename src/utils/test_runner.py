# ""Test runner for category matching flow (scheme B).""

import json
import random
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Import project components.
try:
    from src.parser.product_parser import PromXMLParser
    from src.category_matcher.core import CategoryMatcher
except ImportError:
    # Fallback for direct script execution.
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.parser.product_parser import PromXMLParser
    from src.category_matcher.core import CategoryMatcher


class TestRunner:
    # ""Run categorization tests over sampled products.""
    
    def __init__(self, 
                 xml_file: str = "data/input/prom_export.xml",
                 openai_api_key: Optional[str] = None,
                 output_dir: str = "data/output",
                 load_attributes: bool = False):
        # ""Initialize test runner.""
        self.xml_file = Path(xml_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.load_attributes = load_attributes
        
        self.parser = PromXMLParser(str(self.xml_file))
        
        self.category_matcher = CategoryMatcher(openai_api_key=openai_api_key)
        
        self.total_products = self.parser.get_total_offers_count()
        
        logging.info(f"TestRunner initialized. Total products in XML: {self.total_products}, "
                    f"attributes loading: {self.load_attributes}")
    
    def _get_random_product_indices(self, count: int) -> List[int]:
        """
        Генерирует случайные индексы товаров.
        
        Args:
            count: Количество индексов
            
        Returns:
            Список случайных индексов
        """
        if count >= self.total_products:
            return list(range(self.total_products))
        
        return random.sample(range(self.total_products), count)
    
    def _load_product_by_index(self, index: int) -> Optional[Dict]:
        """
        Загружает товар по индексу.
        
        Args:
            index: Индекс товара
            
        Returns:
            Данные товара или None
        """
        try:
            product_data = self.parser.parse_offer_by_index(index)
            if product_data:
                return product_data.to_dict()
            return None
        except Exception as e:
            logging.error(f"Ошибка загрузки товара по индексу {index}: {e}")
            return None
    
    def run_test(self, 
                 product_count: int,
                 output_file: Optional[str] = None) -> Dict:
        """
        Запускает тест категоризации (схема B).
        
        Args:
            product_count: Количество товаров для тестирования
            output_file: Файл для сохранения результатов
            
        Returns:
            Результаты тестирования
        """
        logging.info(f"Запуск теста для {product_count} товаров")
        
        # Генерируем случайные индексы
        random_indices = self._get_random_product_indices(product_count)
        
        # Подготавливаем структуру результатов
        test_results = {
            "test_config": {
                "scheme": "B",
                "products_count": len(random_indices),
                "timestamp": datetime.now().isoformat(),
                "xml_file": str(self.xml_file),
                "total_products_in_xml": self.total_products,
                "load_attributes": self.load_attributes
            },
            "results": [],
            "summary": {
                "total_processed": 0,
                "successful": 0,
                "rejected": 0,
                "errors": 0,
                "avg_time": 0.0,
                "total_time": 0.0
            }
        }
        
        # Оценка стоимости
        cost_estimate = self.category_matcher.estimate_costs(len(random_indices))
        test_results["cost_estimate"] = cost_estimate
        
        total_time = 0.0
        successful_count = 0
        rejected_count = 0
        error_count = 0
        
        for i, product_index in enumerate(random_indices):
            logging.info(f"Обработка товара {i+1}/{len(random_indices)} (индекс {product_index})")
            
            try:
                # Загружаем товар
                product_data = self._load_product_by_index(product_index)
                if not product_data:
                    logging.warning(f"Не удалось загрузить товар по индексу {product_index}")
                    error_count += 1
                    continue
                
                # Классифицируем товар
                start_time = time.time()
                classification_result = self.category_matcher.classify(
                    product_data, 
                    load_attributes=self.load_attributes
                )
                processing_time = time.time() - start_time
                
                # Формируем результат
                result_item = {
                    "product_index": product_index,
                    "product_name": classification_result["product_name"],
                    "original_category": classification_result["original_category"],
                    "selected_category": classification_result["selected_category"],
                    "processing_time": processing_time,
                    "rejected": classification_result["rejected"],
                    "confidence": classification_result.get("confidence", 0),
                    "reasoning": classification_result.get("reasoning", ""),
                    "candidates_count": classification_result.get("candidates_count", {})
                }
                
                # Добавляем схемо-специфичные данные
                if "hierarchy_probs" in classification_result:
                    result_item["hierarchy_probs"] = classification_result["hierarchy_probs"]
                if "hierarchy_analysis" in classification_result:
                    result_item["hierarchy_analysis"] = classification_result["hierarchy_analysis"]
                
                # Добавляем атрибуты если загружены
                if "epic_attributes" in classification_result:
                    result_item["epic_attributes"] = classification_result["epic_attributes"]
                
                test_results["results"].append(result_item)
                
                # Обновляем статистику
                total_time += processing_time
                if classification_result["rejected"]:
                    rejected_count += 1
                else:
                    successful_count += 1
                
                logging.info(f"Товар обработан за {processing_time:.2f}с, "
                           f"отклонен: {classification_result['rejected']}")
                
            except Exception as e:
                logging.error(f"Ошибка обработки товара {product_index}: {e}")
                error_count += 1
                continue
        
        # Финализируем статистику
        processed_count = successful_count + rejected_count
        test_results["summary"].update({
            "total_processed": processed_count,
            "successful": successful_count,
            "rejected": rejected_count,
            "errors": error_count,
            "avg_time": total_time / processed_count if processed_count > 0 else 0.0,
            "total_time": total_time,
            "success_rate": successful_count / processed_count if processed_count > 0 else 0.0,
            "rejection_rate": rejected_count / processed_count if processed_count > 0 else 0.0
        })
        
        # Сохраняем результаты
        if output_file:
            output_path = self.output_dir / output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(test_results, f, ensure_ascii=False, indent=2)
            logging.info(f"Результаты сохранены в {output_path}")
        
        logging.info(f"Тест завершен. "
                    f"Успешно: {successful_count}, Отклонено: {rejected_count}, "
                    f"Ошибки: {error_count}, Среднее время: {test_results['summary']['avg_time']:.2f}с")
        
        return test_results
    
    def get_system_info(self) -> Dict:
        # ""Возвращает информацию о системе тестирования.""
        return {
            "xml_file": str(self.xml_file),
            "total_products": self.total_products,
            "category_matcher_info": self.category_matcher.get_system_info(),
            "output_directory": str(self.output_dir)
        }
