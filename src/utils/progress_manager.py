# ""Track and persist product processing progress.""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime


class ProgressManager:
    # ""Manage processing progress state.""
    
    def __init__(self, progress_file: str = "data/output/processing_progress.json"):
        # ""Initialize progress manager.""
        self.progress_file = Path(progress_file)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.progress_data: Optional[Dict] = self._load_progress()
        
        if self.progress_data:
            logging.info(f"ProgressManager initialized, loaded progress: {len(self.progress_data.get('processed_indices', []))} processed products")
        else:
            logging.info("ProgressManager initialized, no saved progress found")
    
    def _load_progress(self) -> Optional[Dict]:
        # ""Load progress from file.""
        if not self.progress_file.exists():
            return None
        
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else None
        except (IOError, json.JSONDecodeError) as e:
            logging.warning(f"Failed to load progress file {self.progress_file}: {e}")
            return None
    
    def save_progress(self,
                     last_index: int,
                     processed_indices: List[int],
                     successful_count: int,
                     rejected_count: int,
                     no_photos_count: int,
                     output_file: str,
                     started_at: Optional[str] = None) -> None:
        # ""Save current processing progress.""
        if not self.progress_data:
            self.progress_data = {}
            if started_at:
                self.progress_data["started_at"] = started_at
            else:
                self.progress_data["started_at"] = datetime.now().isoformat()
        
        self.progress_data["last_index"] = last_index
        self.progress_data["processed_indices"] = sorted(list(set(processed_indices)))
        self.progress_data["successful_count"] = successful_count
        self.progress_data["rejected_count"] = rejected_count
        self.progress_data["no_photos_count"] = no_photos_count
        self.progress_data["output_file"] = output_file
        self.progress_data["last_saved_at"] = datetime.now().isoformat()
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress_data, f, ensure_ascii=False, indent=2)
            logging.info(f"Progress saved: {len(processed_indices)} products processed, last index: {last_index}")
        except IOError as e:
            logging.error(f"Failed to save progress file {self.progress_file}: {e}")
    
    def reset_for_new_output(self, output_file: str) -> None:
        # ""Reset progress for a new output file.""
        logging.info(f"Resetting progress. New output file: {output_file}")
        self.progress_data = None
        self.save_progress(
            last_index=-1,
            processed_indices=[],
            successful_count=0,
            rejected_count=0,
            no_photos_count=0,
            output_file=output_file,
            started_at=datetime.now().isoformat()
        )
    
    def load_progress(self) -> Optional[Dict]:
        # ""Return saved progress data.""
        return self.progress_data
    
    def is_processed(self, product_index: int) -> bool:
        # ""Check whether a product index is already processed.""
        if not self.progress_data:
            return False
        
        processed_indices = self.progress_data.get("processed_indices", [])
        return product_index in processed_indices
    
    def get_processed_indices(self) -> Set[int]:
        # ""Return a set of processed product indices.""
        if not self.progress_data:
            return set()
        
        return set(self.progress_data.get("processed_indices", []))
    
    def clear_progress(self) -> None:
        # ""Clear progress by deleting the progress file.""
        if self.progress_file.exists():
            try:
                self.progress_file.unlink()
                logging.info("Progress file deleted")
            except IOError as e:
                logging.error(f"Failed to delete progress file {self.progress_file}: {e}")
        
        self.progress_data = None
    
    def has_progress(self) -> bool:
        # ""Check whether saved progress exists.""
        return self.progress_data is not None
    
    def get_output_file(self) -> Optional[str]:
        # ""Return output file path from saved progress.""
        if not self.progress_data:
            return None
        return self.progress_data.get("output_file")

