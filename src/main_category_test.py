# ""Main script for testing the product categorization system.""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to import path.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.test_runner import TestRunner


def setup_logging(verbose: bool = False):
    # ""Configure logging handlers and log levels.""
    level = logging.DEBUG if verbose else logging.INFO
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    log_file = Path("data/output/category_test.log")
    log_file.parent.mkdir(exist_ok=True)
    
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


def validate_environment(load_attributes: bool = False):
    # ""Validate required environment variables and files.""
    errors = []
    
    if not os.getenv('OPENAI_API_KEY'):
        errors.append("Environment variable OPENAI_API_KEY is not set")
    
    if load_attributes and not os.getenv('EPIC_API_KEY'):
        errors.append("Environment variable EPIC_API_KEY is not set (required for attribute loading)")
    
    required_files = [
        "data/input/prom_export.xml",
        "data/other/epic_categories.json",
        "data/other/epic_categories_hierarchical.json"
    ]
    
    if load_attributes:
        required_files.append("data/other/epic_required_attributes.json")
    
    for file_path in required_files:
        if not Path(file_path).exists():
            errors.append(f"File not found: {file_path}")
    
    if errors:
        print("CONFIGURATION ERRORS:")
        for error in errors:
            print(f"  - {error}")
        print("\\nFix the errors and run again.")
        sys.exit(1)
    
    print("OK: Configuration validated successfully")


def main():
    # ""CLI entry point.""
    parser = argparse.ArgumentParser(
        description="Product categorization system test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:

  # Test for 50 products
  python src/main_category_test.py --count 50

  # Test with verbose logging
  python src/main_category_test.py --count 30 --verbose

  # Test with custom output file
  python src/main_category_test.py --count 20 --output my_test_results
        """
    )
    
    parser.add_argument(
        '--count',
        type=int,
        default=50,
        help='Number of products to test (default: 50)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='category_test',
        help='Output file prefix (default: category_test)'
    )
    
    parser.add_argument(
        '--xml-file',
        type=str,
        default='data/input/prom_export.xml',
        help='Path to the product XML file'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose logging'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration without running tests'
    )
    
    parser.add_argument(
        '--load-attributes',
        action='store_true',
        help='Load Epicentr attributes for selected categories'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    print("Product categorization system")
    print("=" * 50)
    
    validate_environment(load_attributes=args.load_attributes)
    
    if args.dry_run:
        print("OK: Dry run completed successfully")
        return
    
    try:
        print("Initializing system...")
        test_runner = TestRunner(
            xml_file=args.xml_file,
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            load_attributes=args.load_attributes
        )
        
        system_info = test_runner.get_system_info()
        print(f"Total products in XML: {system_info['total_products']}")
        print(f"Products to test: {args.count}")
        print(f"Results will be saved to: {system_info['output_directory']}")
        
        cost_estimate = test_runner.category_matcher.estimate_costs(args.count)
        print(f"Estimated cost: ${cost_estimate['total']:.4f} "
              f"(${cost_estimate['cost_per_product']:.4f} per product)")
        
        print("\\n" + "=" * 50)
        
        print("Starting test...")
        
        result = test_runner.run_test(
            product_count=args.count,
            output_file=f"{args.output}.json"
        )
        
        summary = result.get("summary", {})
        print("\\nRESULT:")
        print("-" * 30)
        print(f"Successfully processed: {summary.get('successful', 0)} "
              f"({summary.get('success_rate', 0)*100:.1f}%)")
        print(f"Rejected: {summary.get('rejected', 0)} "
              f"({summary.get('rejection_rate', 0)*100:.1f}%)")
        print(f"Errors: {summary.get('errors', 0)}")
        print(f"Average time: {summary.get('avg_time', 0):.2f}s")
        print(f"Total time: {summary.get('total_time', 0):.1f}s")
        
        if result.get("results"):
            print("\\nRESULT EXAMPLES:")
            print("-" * 30)
            
            successful_results = [r for r in result["results"] if not r["rejected"]][:3]
            for i, res in enumerate(successful_results, 1):
                print(f"{i}. {res['product_name'][:50]}...")
                if res['selected_category']:
                    print(f"   -> {res['selected_category']['name']}")
                    print(f"   Confidence: {res['confidence']}%")
                print()
        
        print("Testing completed successfully!")
        
    except KeyboardInterrupt:
        print("\\nTesting interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Critical error: {e}", exc_info=True)
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
