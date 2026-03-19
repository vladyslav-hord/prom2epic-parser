# Product Processing Pipeline

Automated pipeline for parsing, normalizing, and categorizing product data from Prom.ua XML exports for integration with the Epic marketplace.

## Overview

This project processes product listings through a multi-stage pipeline:

1. **Parse** - Extract product data from XML
2. **Normalize** - Translate and clean product information
3. **Classify** - Match products to Epic categories using semantic search + LLM
4. **Map Attributes** - Fill required attributes for each category
5. **Export** - Generate Epic-compatible XML

The categorization uses a hybrid approach combining local embeddings (sentence-transformers), OpenAI reranking, and GPT for final selection.

## Tech Stack

- **Python 3.9+**
- **Semantic Search**: sentence-transformers (multilingual-e5-large)
- **LLM**: OpenAI GPT-4o-mini
- **Translation**: DeepL API
- **Testing**: pytest

## Project Structure

```
├── src/
│   ├── category_matcher/     # Semantic search + LLM categorization
│   ├── parser/                # XML parsing
│   ├── utils/                 # Data normalization, attributes, export
│   └── main_process_products.py  # Main entry point
├── data/
│   ├── input/                 # Source XML files
│   ├── output/                # Generated XML + logs
│   └── other/                 # Caches, categories, attributes
└── tests/                     # Unit and integration tests
```

## Setup

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd prom2epic_parser_backup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required:
- `OPENAI_API_KEY` - For category classification
- `EPIC_API_KEY` - For loading product attributes

Optional:
- `DEEPL_API_KEY` - For translation (fallback to basic translation if not set)

### 3. Prepare Input Data

Place your Prom.ua XML export in `data/input/prom_export.xml`

## Usage

### Basic Run

Process products with default settings (random order, load attributes):

```bash
python src/main_process_products.py --input data/input/prom_export.xml
```

### Options

```bash
# Process sequentially from index 100
python src/main_process_products.py --sequential --start-index 100

# Skip attribute loading
python src/main_process_products.py --no-attributes

# Custom output file
python src/main_process_products.py --output data/output/my_products.xml

# Verbose logging
python src/main_process_products.py --verbose
```

### Resume Processing

The pipeline automatically saves progress. If interrupted, rerun the same command to continue from the last checkpoint.

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_category_matcher.py
```

## How It Works

### Category Matching (Scheme B)

1. **Stage 1**: Semantic search with hierarchy weights
   - Generate embeddings for product context
   - Search 100 most similar categories
   - Apply super-category probability weights

2. **Stage 2**: OpenAI reranking
   - Rerank top candidates using OpenAI embeddings
   - Select top 15 most relevant

3. **Stage 3**: LLM final selection
   - GPT-4o-mini analyzes product and candidates
   - Returns selected category or rejection reason

4. **Retry** (if rejected):
   - Ask GPT for alternative category suggestions
   - Search system for suggested categories
   - Rerun selection process

### Attribute Filling

For each categorized product:
1. Load required attributes from Epic API
2. Match input parameters to attribute names
3. For missing values, use LLM to suggest appropriate values
4. Apply semantic search to find correct option codes
5. Fill brand and country with fallback handling

## Configuration

### Cache Directories

- `data/other/` - Embeddings cache, translations
- `data/other/attributes_values/` - API response cache

### Output Files

- `data/output/products_*.xml` - Processed products
- `data/output/rejected_products.json` - Rejected items log
- `data/output/no_photos_products.json` - Skipped items (no images)
- `data/output/processing_progress.json` - Resume checkpoint

## Performance Notes

- First run builds embeddings cache (~2-5 min for 5K categories)
- Subsequent runs use cached embeddings
- Processing speed: ~30-60 seconds per product (with attributes)
- Auto-saves every 5 products

## Known Limitations

- Requires valid API keys for OpenAI and Epic
- Large product sets may incur API costs
- Translation quality depends on DeepL availability

## Contributing

This is a course project for EPAM. For questions or suggestions, open an issue.

## License

MIT
