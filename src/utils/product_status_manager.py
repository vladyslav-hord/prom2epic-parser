import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class _BaseProductStatusManager:
    # Shared JSON-list persistence for product status records.
    def __init__(self, file_path: str, status_name: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.status_name = status_name
        self.items: List[Dict] = self._load_items()

        logging.info(
            f"{self.__class__.__name__} initialized, loaded "
            f"{len(self.items)} {self.status_name} products"
        )

    def _load_items(self) -> List[Dict]:
        if not self.file_path.exists():
            return []

        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else []
        except (IOError, json.JSONDecodeError) as exc:
            logging.warning(f"Failed to load file {self.file_path}: {exc}")
            return []

    def _exists(self, product_id: str) -> bool:
        return any(item.get("product_id") == product_id for item in self.items)

    def save(self) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as file:
                json.dump(self.items, file, ensure_ascii=False, indent=2)
            logging.info(f"{self.status_name.title()} products list saved: {len(self.items)} products")
        except IOError as exc:
            logging.error(f"Failed to save file {self.file_path}: {exc}")

    def clear(self) -> None:
        self.items.clear()
        logging.info(f"{self.status_name.title()} products list cleared")


class RejectedProductsManager(_BaseProductStatusManager):
    # Manage products rejected during categorization.
    def __init__(self, rejected_file: str = "data/output/rejected_products.json"):
        super().__init__(file_path=rejected_file, status_name="rejected")

    def add_rejected(self, product_data: Dict, reason: Optional[str] = None) -> None:
        product_id = product_data.get("id", "")
        if self._exists(product_id):
            logging.debug(f"Product {product_id} is already in rejected list")
            return

        self.items.append(
            {
                "product_id": product_id,
                "product_name": product_data.get("name", ""),
                "product_name_ua": product_data.get("name_ua", ""),
                "original_category": product_data.get("category_name", ""),
                "reason": reason or "Category not found",
                "rejected_at": datetime.now().isoformat(),
            }
        )
        logging.info(f"Product {product_id} added to rejected list: {reason}")

    def is_rejected(self, product_id: str) -> bool:
        return self._exists(product_id)

    def get_rejected_count(self) -> int:
        return len(self.items)


class NoPhotosProductsManager(_BaseProductStatusManager):
    # Manage products skipped due to missing photos.
    def __init__(self, no_photos_file: str = "data/output/no_photos_products.json"):
        super().__init__(file_path=no_photos_file, status_name="no-photo")

    def add_no_photos(self, product_data: Dict, reason: Optional[str] = None) -> None:
        product_id = product_data.get("id", "")
        if self._exists(product_id):
            logging.debug(f"Product {product_id} is already in no-photo list")
            return

        self.items.append(
            {
                "product_id": product_id,
                "product_name": product_data.get("name", ""),
                "product_name_ua": product_data.get("name_ua", ""),
                "reason": reason or "No photos",
                "skipped_at": datetime.now().isoformat(),
            }
        )
        logging.info(f"Product {product_id} added to no-photo list: {reason}")

    def is_no_photos(self, product_id: str) -> bool:
        return self._exists(product_id)

    def get_no_photos_count(self) -> int:
        return len(self.items)
