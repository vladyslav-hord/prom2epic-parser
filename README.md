# Product Processing Pipeline

Takes product data from Prom.ua XML exports and prepares it for the Epic marketplace. Handles translation, automatic categorization, and attribute mapping.

## What it does

Parse XML → Translate to Ukrainian → Find matching category → Fill attributes → Export to Epic format

The categorization works in 3 stages:
1. Fast semantic search narrows down to 100 categories
2. OpenAI reranking picks top 15
3. GPT makes the final call

If nothing fits, it asks GPT for suggestions and tries again.

## Stack

- Python 3.9+
- sentence-transformers for semantic search
- OpenAI API for smart matching
- DeepL for translation

## Quick Start

```bash
# Clone and setup
git clone <your-repo>
cd prom2epic_parser_backup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Add your API keys
cp .env.example .env
# Edit .env with your keys

# Run it
python src/main_process_products.py --input data/input/prom_export.xml
```

### API Keys You Need

Create a `.env` file:
```
OPENAI_API_KEY=your_key_here
EPIC_API_KEY=your_key_here
DEEPL_API_KEY=your_key_here  # optional
```

## Usage

Basic:
```bash
python src/main_process_products.py --input data/input/prom_export.xml
```

More options:
```bash
# Start from specific product
python src/main_process_products.py --sequential --start-index 100

# Skip attributes to go faster
python src/main_process_products.py --no-attributes

# Save to custom file
python src/main_process_products.py --output data/output/my_products.xml
```

**Resume:** If you stop the script, just run it again - it remembers where it left off.

## Project Structure

```
src/
├── category_matcher/   # Smart categorization
├── parser/             # XML handling
├── utils/              # Translation, attributes, export
└── main_process_products.py

data/
├── input/              # Put your XML here
├── output/             # Results end up here
└── other/              # Caches and configs
```

## How Categorization Works

**Stage 1:** Semantic search
- Converts product description to embeddings
- Finds 100 closest categories
- Weighs by super-category match

**Stage 2:** OpenAI rerank  
- Takes top 100, reranks with better embeddings
- Keeps 15 best matches

**Stage 3:** GPT decides
- Looks at product + 15 categories
- Picks the best one or says "none fit"
- If rejected, suggests alternatives and retries

**Attribute mapping:**
- Matches your product params to Epic's attributes
- Uses LLM when data is missing
- Semantic search for dropdown values
- Always fills brand and country

## Output

After processing you get:
- `products_*.xml` - Ready for Epic
- `rejected_products.json` - What didn't match
- `no_photos_products.json` - Skipped (no images)
- `processing_progress.json` - Resume data

## Performance

- First run: ~2-5 min to build embeddings cache
- After that: ~30-60 sec per product
- Auto-saves every 5 products
- Costs depend on OpenAI usage

## Testing

```bash
pytest                           # run all tests
pytest --cov=src                 # with coverage
pytest tests/test_specific.py    # single file
```

## Notes

- Needs valid OpenAI and Epic API keys
- Translation works without DeepL but quality is lower
- Check costs before running on large datasets

## License

MIT
