# ""Main application module for parsing Prom.ua products.""

import json
from pathlib import Path
from parser import parse_single_product, get_products_iterator
from utils import ProductDataNormalizer


def main() -> None:
    # ""Run the main parsing demo workflow.""
    xml_file = Path("data/input/prom_export.xml")
    
    if not xml_file.exists():
        print(f"File {xml_file} was not found!")
        return
    
    print("Parsing and normalizing the first product...")
    
    normalizer = ProductDataNormalizer()
    
    product = parse_single_product(str(xml_file), product_index=0)
    
    if product:
        print("Original product data:")
        print(json.dumps(product, ensure_ascii=False, indent=2))
        
        print("\n" + "="*60 + "\n")
        
        normalized_product = normalizer.normalize_product_data(product)
        
        print("Normalized product data:")
        print(json.dumps(normalized_product, ensure_ascii=False, indent=2))
        
        stats = normalizer.get_normalization_stats()
        print(f"\nTranslation stats: {stats}")
    else:
        print("Product was not found or is unavailable")


def parse_products_example() -> None:
    # ""Show sequential parsing of a few products.""
    xml_file = Path("data/input/prom_export.xml")
    
    print("Parsing the first 3 products...")
    
    for i, product in enumerate(get_products_iterator(str(xml_file))):
        if i >= 3:
            break
            
        print(f"\n--- Product {i + 1} ---")
        print(f"ID: {product['id']}")
        print(f"Name: {product['name']}")
        print(f"Price: {product['price']} UAH")
        print(f"Category: {product['category_name']}")
        print(f"Images: {len(product['pictures'])}")
        print(f"Parameters: {len(product['params'])}")


def normalize_products_example() -> None:
    # ""Show normalization for a few products.""
    xml_file = Path("data/input/prom_export.xml")
    
    if not xml_file.exists():
        print(f"File {xml_file} was not found!")
        return
    
    print("Normalizing the first 2 products...")
    
    normalizer = ProductDataNormalizer()
    
    for i, product in enumerate(get_products_iterator(str(xml_file))):
        if i >= 2:
            break
            
        print(f"\n{'='*60}")
        print(f"PRODUCT {i + 1}: {product.get('name', 'Untitled')}")
        print('='*60)
        
        print(f"Original category: {product.get('category_name', 'Not specified')}")
        print("Original parameters:")
        for param_name, param_value in product.get('params', {}).items():
            print(f"  {param_name}: {param_value}")
        
        normalized_product = normalizer.normalize_product_data(product)
        
        print(f"\nNormalized category: {normalized_product.get('category_name', 'Not specified')}")
        print("Normalized parameters:")
        for param_name, param_value in normalized_product.get('params', {}).items():
            print(f"  {param_name}: {param_value}")
    
    stats = normalizer.get_normalization_stats()
    print(f"\n{'='*60}")
    print("TRANSLATION STATS:")
    print(f"Categories in cache: {stats.get('categories', 0)}")
    print(f"Parameters in cache: {stats.get('params', 0)}")
    print(f"General translations in cache: {stats.get('general', 0)}")
    print(f"Total translations: {stats.get('total', 0)}")
    print(f"DeepL API available: {'Yes' if stats.get('deepl_available') else 'No'}")


if __name__ == "__main__":
    main()
    print("\n" + "="*50 + "\n")
    parse_products_example()
    print("\n" + "="*50 + "\n")
    normalize_products_example()

