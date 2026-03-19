# ""Run full product processing: parse -> normalize -> categorize -> attributes -> XML export.""

import argparse
import logging
import os
import sys
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to import path.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.product_processor import ProductProcessor
from src.utils.progress_manager import ProgressManager


def setup_logging(verbose: bool = False):
    # ""Configure logging handlers and log levels.""
    level = logging.DEBUG if verbose else logging.INFO
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    log_file = Path("data/output/processing.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Reduce noisy logs from third-party libraries.
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def validate_environment(load_attributes: bool = True):
    # ""Validate required environment variables.""
    missing_keys = []
    
    deepl_key = os.getenv("DEEPL_API_KEY")
    if not deepl_key:
        logging.warning("DEEPL_API_KEY is not set - translations will be skipped")
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        missing_keys.append("OPENAI_API_KEY")
    
    if load_attributes:
        epic_key = os.getenv("EPIC_API_KEY")
        if not epic_key:
            missing_keys.append("EPIC_API_KEY")
    
    if missing_keys:
        logging.error(f"Missing required environment variables: {', '.join(missing_keys)}")
        logging.error("Set them with: setx VARIABLE_NAME value")
        return False
    
    return True


def process_products(xml_file_path: str,
                     random_selection: bool = True,
                     start_index: int = 0,
                     load_attributes: bool = True,
                     output_file: Optional[str] = None):
    """
    Process all available products through the full pipeline.
    
    Args:
        xml_file_path: Input XML file path.
        random_selection: Whether to shuffle product processing order.
        start_index: Start index for sequential mode.
        load_attributes: Whether to load attributes after categorization.
        output_file: Output XML file path (optional).
    """
    deepl_api_key = os.getenv("DEEPL_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    epic_api_key = os.getenv("EPIC_API_KEY") if load_attributes else None
    
    logging.info("Initializing ProductProcessor...")
    processor = ProductProcessor(
        deepl_api_key=deepl_api_key,
        openai_api_key=openai_api_key,
        epic_api_key=epic_api_key,
        load_attributes=load_attributes
    )
    
    progress_manager = ProgressManager()
    
    from src.parser.product_parser import PromXMLParser
    parser = PromXMLParser(xml_file_path)
    total_products = parser.get_total_offers_count()
    
    saved_progress = progress_manager.load_progress()
    append_mode = False
    
    if output_file:
        if saved_progress and saved_progress.get("output_file") != output_file:
            logging.info(f"New output file selected: {output_file}. Progress will be reset.")
            progress_manager.reset_for_new_output(output_file)
            saved_progress = progress_manager.load_progress()
        else:
            if saved_progress:
                logging.info(f"Resuming work with file: {output_file}")
            else:
                logging.info(f"Using provided output file: {output_file}")
            append_mode = True if saved_progress else False
    else:
        if saved_progress and saved_progress.get("output_file"):
            saved_output_file = saved_progress.get("output_file")
            if not sys.stdin.isatty():
                logging.info(
                    "Saved progress detected, but input is non-interactive. "
                    f"Continuing to append to existing file: {saved_output_file}"
                )
                output_file = saved_output_file
                append_mode = True
            else:
                while True:
                    user_choice = input(
                        "Saved progress detected.\n"
                        f"Continue writing to existing file ({saved_output_file})? [Y/n]: "
                    ).strip().lower()
                    if user_choice in ("", "y", "yes", "д", "да"):
                        output_file = saved_output_file
                        append_mode = True
                        break
                    if user_choice in ("n", "no", "н", "нет"):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_file = f"data/output/products_{timestamp}.xml"
                        logging.info(f"Created new file: {output_file}. Progress will be reset.")
                        progress_manager.reset_for_new_output(output_file)
                        saved_progress = progress_manager.load_progress()
                        break
                    logging.info("Please enter 'Y' (yes) or 'N' (no).")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"data/output/products_{timestamp}.xml"
            logging.info(f"Created new file: {output_file}")
    
    processed_indices_set = progress_manager.get_processed_indices() if saved_progress else set()
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    append_to_output = append_mode
    
    processed_products = []
    if append_mode and output_path.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(output_path)
            root = tree.getroot()
            offers = root.find(".//offers")
            if offers is not None:
                existing_count = len(list(offers.findall("offer")))
                logging.info(f"Found {existing_count} already processed products in file {output_file}")
        except Exception as e:
            logging.warning(f"Failed to load existing products from {output_file}: {e}")
    
    if saved_progress:
        successful_count = saved_progress.get("successful_count", 0)
        rejected_count = saved_progress.get("rejected_count", 0)
        no_photos_count = saved_progress.get("no_photos_count", 0)
        start_time = saved_progress.get("started_at", datetime.now().isoformat())
        logging.info(
            f"Resuming: successful={successful_count}, rejected={rejected_count}, no_photos={no_photos_count}"
        )
    else:
        successful_count = 0
        rejected_count = 0
        no_photos_count = 0
        start_time = datetime.now().isoformat()
    
    error_count = 0
    
    base_start_index = start_index
    if saved_progress:
        last_index = saved_progress.get("last_index")
        if last_index is not None:
            base_start_index = max(start_index, last_index + 1)
            logging.info(f"Resuming from index {base_start_index} (last processed: {last_index})")
    
    if random_selection:
        available_indices = [
            idx for idx in range(base_start_index, total_products)
            if idx not in processed_indices_set
        ]
        random.shuffle(available_indices)
        selected_indices = available_indices
        logging.info(
            f"Selected {len(selected_indices)} new products from {len(available_indices)} available "
            f"(already processed: {len(processed_indices_set)})"
        )
    else:
        selected_indices = [
            idx for idx in range(base_start_index, total_products)
            if idx not in processed_indices_set
        ]
        logging.info(
            f"Processing from index {base_start_index}, selected {len(selected_indices)} new products "
            f"(already processed: {len(processed_indices_set)})"
        )
    
    if not selected_indices:
        logging.warning("No new products to process. All products are already processed.")
        total_processed = successful_count + rejected_count + no_photos_count
        return {
            "total": total_processed,
            "successful": successful_count,
            "rejected": rejected_count,
            "no_photos": no_photos_count,
            "errors": error_count,
            "output_file": output_file
        }
    
    all_processed_indices = list(processed_indices_set)
    
    logging.info(f"Starting processing for {len(selected_indices)} products...")
    
    for i, product_index in enumerate(selected_indices):
        try:
            logging.info(f"Processing product {i+1}/{len(selected_indices)} (index {product_index})...")
            
            product_data = processor.process_single_product(xml_file_path, product_index)
            
            if product_data:
                if product_data.get("rejected"):
                    rejected_count += 1
                    logging.warning(
                        f"Product {product_index} rejected: "
                        f"{product_data.get('classification', {}).get('reasoning', 'Unknown reason')}"
                    )
                else:
                    successful_count += 1
                    logging.info(f"Product {product_index} processed successfully")
                
                processed_products.append(product_data)
                all_processed_indices.append(product_index)
            else:
                try:
                    temp_product = parser.parse_offer_by_index(product_index)
                    if temp_product:
                        product_id = getattr(temp_product, "id", str(product_index))
                        if processor.no_photos_manager.is_no_photos(product_id):
                            no_photos_count += 1
                            logging.info(f"Product {product_index} skipped: no photos")
                        else:
                            error_count += 1
                            logging.error(f"Failed to process product {product_index}")
                    else:
                        error_count += 1
                        logging.error(f"Failed to load product {product_index}")
                except Exception:
                    error_count += 1
                    logging.error(f"Failed to process product {product_index}")
                
                all_processed_indices.append(product_index)
            
            total_processed = successful_count + rejected_count + no_photos_count
            if total_processed > 0 and total_processed % 5 == 0:
                logging.info(f"Auto-save: {total_processed} products processed")
                
                processor.xml_exporter.export_products(
                    processed_products, str(output_path), append=append_to_output
                )
                append_to_output = True
                
                last_index = product_index
                progress_manager.save_progress(
                    last_index=last_index,
                    processed_indices=all_processed_indices,
                    successful_count=successful_count,
                    rejected_count=rejected_count,
                    no_photos_count=no_photos_count,
                    output_file=output_file,
                    started_at=start_time
                )
                
                processed_products = []
                
        except Exception as e:
            error_count += 1
            logging.error(f"Error while processing product {product_index}: {e}", exc_info=True)
            all_processed_indices.append(product_index)
    
    if processed_products:
        logging.info(f"Final save of {len(processed_products)} products...")
        processor.xml_exporter.export_products(
            processed_products, str(output_path), append=append_to_output
        )
    
    total_processed = successful_count + rejected_count + no_photos_count
    logging.info("=" * 60)
    logging.info("PROCESSING STATISTICS")
    logging.info("=" * 60)
    logging.info(f"Total processed: {total_processed}")
    logging.info(f"Successful: {successful_count}")
    logging.info(f"Rejected: {rejected_count}")
    logging.info(f"No photos: {no_photos_count}")
    logging.info(f"Errors: {error_count}")
    
    if all_processed_indices:
        last_index = max(all_processed_indices)
        progress_manager.save_progress(
            last_index=last_index,
            processed_indices=all_processed_indices,
            successful_count=successful_count,
            rejected_count=rejected_count,
            no_photos_count=no_photos_count,
            output_file=output_file,
            started_at=start_time
        )
    
    stats_file = output_path.with_suffix('.stats.txt')
    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write("PROCESSING STATISTICS\n")
        f.write("=" * 60 + "\n")
        f.write(f"Processing date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Input file: {xml_file_path}\n")
        f.write(f"Output file: {output_file}\n")
        f.write(f"Total processed: {total_processed}\n")
        f.write(f"Successful: {successful_count}\n")
        f.write(f"Rejected: {rejected_count}\n")
        f.write(f"No photos: {no_photos_count}\n")
        f.write(f"Errors: {error_count}\n")
    
    logging.info(f"Statistics saved to {stats_file}")
    logging.info(f"Processing completed. Results saved to {output_file}")
    
    return {
        "total": total_processed,
        "successful": successful_count,
        "rejected": rejected_count,
        "no_photos": no_photos_count,
        "errors": error_count,
        "output_file": output_file
    }


def main():
    # ""CLI entry point.""
    parser = argparse.ArgumentParser(
        description="Full product processing: parsing -> normalization -> categorization -> attributes -> XML export"
    )
    
    parser.add_argument(
        "--input",
        type=str,
        default="data/input/prom_export.xml",
        help="Input XML file path (default: data/input/prom_export.xml)"
    )
    
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start product index (default: 0)"
    )
    
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Process products sequentially (default: random selection)"
    )
    
    parser.add_argument(
        "--no-attributes",
        action="store_true",
        help="Do not load attributes after categorization"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            "Output XML file path. Default behavior: continue writing to the file from saved progress "
            "or create a new data/output/products_TIMESTAMP.xml file"
        )
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging"
    )
    
    args = parser.parse_args()
    
    setup_logging(verbose=args.verbose)
    
    load_attributes = not args.no_attributes
    if not validate_environment(load_attributes=load_attributes):
        sys.exit(1)
    
    input_path = Path(args.input)
    if not input_path.exists():
        logging.error(f"Input file not found: {args.input}")
        sys.exit(1)
    
    random_selection = not args.sequential
    
    try:
        stats = process_products(
            xml_file_path=str(input_path),
            random_selection=random_selection,
            start_index=args.start_index,
            load_attributes=load_attributes,
            output_file=args.output
        )
        
        logging.info("=" * 60)
        logging.info("PROCESSING COMPLETED SUCCESSFULLY")
        logging.info("=" * 60)
        logging.info(f"Successfully processed: {stats['successful']}/{stats['total']}")
        logging.info(f"Results saved to: {stats['output_file']}")
        
    except KeyboardInterrupt:
        logging.warning("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Critical error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

