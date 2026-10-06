# Prom.ua → Epicentr Product Migration Pipeline

> **Archived commercial project / historical snapshot.**
>
> This codebase supported a real commercial migration of approximately **50,000 products** from Prom.ua to Epicentr. It is preserved for portfolio and historical reference, not as a maintained integration.

## Snapshot status

This repository is **not guaranteed to run today**. Since the original migration:

- external APIs and their contracts may have changed;
- private source feeds, category dictionaries, caches, and other production data are not included;
- API credentials and the original deployment environment are not included;
- the current Epicentr API is outside the scope of this snapshot.

The repository therefore documents the original implementation and selected safety fixes; cloning it, installing dependencies, and supplying API keys is not presented as a complete reproduction path.

## What it did

The pipeline transformed Prom.ua XML exports into an Epicentr-oriented product feed:

`XML parsing → normalization/translation → category matching → attribute mapping → XML export`

Category matching used three stages:

1. local semantic search to reduce the category space;
2. embedding-based reranking;
3. LLM selection from the supplied candidate set.

Products without a defensible category or required attribute mapping were separated for rejection or manual review.

## Architecture

- `src/parser/` — streaming Prom.ua XML parsing.
- `src/category_matcher/` — semantic retrieval, hierarchy weighting, reranking, and constrained LLM selection.
- `src/utils/attributes_filler/` — mapping source parameters to Epicentr attribute dictionaries.
- `src/utils/product_processor.py` — orchestration for one product and rejection handling.
- `src/main_process_products.py` — batch processing, progress persistence, and resume behavior.
- `src/utils/xml_exporter.py` — Epicentr-oriented XML generation.
- `data/` — historical dictionaries, caches, samples, and generated artifacts where included.

## Historical stack

- Python 3.9+
- `sentence-transformers` / PyTorch for semantic search
- OpenAI APIs for reranking and constrained selection
- DeepL for optional translation
- ElementTree for XML parsing and export

## Trade-offs / lessons learned

- **Hybrid matching was practical at catalog scale.** Local retrieval reduced LLM cost, but every LLM output still needed validation against deterministic candidate sets and dictionaries.
- **Fail-closed data quality matters.** Guessing required marketplace attributes can produce syntactically valid but commercially incorrect listings; unresolved values should go to manual review.
- **Resume state must track explicit completed items.** A single “last index” is insufficient when processing order is randomized or failures must be retried.
- **Marketplace integrations age quickly.** API contracts, taxonomies, credentials, and private source data make long-term reproducibility difficult without a maintained test environment.
- **XML libraries should own escaping.** Pre-escaping text before ElementTree serialization causes double-escaped output.

## Historical outputs

The original workflow produced:

- `products_*.xml` — generated product feeds;
- `rejected_products.json` — products requiring rejection/manual review;
- `no_photos_products.json` — products skipped because images were missing;
- `processing_progress.json` — batch resume state.

## License

MIT
