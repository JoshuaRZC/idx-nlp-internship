# Week 5 Report

## Overview

This week focused on semantic search for real estate listing remarks. The main work was to build embedding-based retrieval with FAISS, add a BM25 keyword baseline, compare two sentence-transformer models, and review search quality and latency in a notebook.

## Week 5 Semantic Search

- Built a reusable `SemanticSearcher` for listing remarks.
- Added support for:
  - configurable sentence-transformers models.
  - FAISS inner-product search over normalized embeddings.
  - saved and loaded FAISS indexes, embeddings, and metadata.
  - candidate-only reranking for later integration with SQL filters.
- Added a `BM25Searcher` as a keyword-search baseline.
- Generated a fixed 10k listing sample for repeatable Week 5 evaluation.
- Built local semantic indexes for:
  - `sentence-transformers/all-MiniLM-L6-v2`: 384-dimensional embeddings.
  - `sentence-transformers/all-mpnet-base-v2`: 768-dimensional embeddings.
- Built a full MiniLM index over all non-empty `rets_property.L_Remarks`.
- Kept higher-level search modes out of scope for now so Week 5 remains focused on retrieval quality, latency, and model comparison.

## Current Artifacts

- `src/real_estate_nlp/semantic_search.py`
  - Contains the embedding-based searcher, FAISS index handling, save/load logic, model configuration, and candidate reranking.

- `src/real_estate_nlp/keyword_search.py`
  - Contains the BM25 keyword baseline used for Week 5 comparison.

- `scripts/generate_semantic_sample.py`
  - Generates the fixed 10k semantic-search sample from the local MySQL database.

- `scripts/build_semantic_index.py`
  - Builds FAISS indexes for either the 10k sample or the full listing remark set.
  - Supports `--model-name`, `--local-files-only`, and `--batch-size`.

- `data/processed/listing_semantic_sample_10k.csv`
  - Local generated sample with 10,000 listing remarks.
  - Contains 9 fields, including listing metadata, `remarks`, and `remarks_cleaned`.
  - Ignored by Git.

- `data/models/semantic/`
  - Local generated semantic-search indexes, embeddings, and metadata.
  - Ignored by Git.
  - Current local indexes:
    - MiniLM sample index: 10,000 listings.
    - MiniLM full index: 52,794 listings.
    - MPNet sample index: 10,000 listings.

- `notebooks/05_semantic_search_evaluation.ipynb`
  - Compares MiniLM, MPNet, and BM25.
  - Includes retrieval examples, latency checks, graded proxy relevance scoring, Precision@5, NDCG@5, and MRR.

- `tests/test_week5.py`
  - Validates semantic-search behavior with a fake embedding model, candidate reranking, save/load behavior, BM25 search, tokenization, and runtime model options.

## Validation

- Semantic sample:
  - 10,000 rows.
  - 0 missing `remarks_cleaned` values.
- Full database index:
  - 52,794 non-empty listing remarks indexed with MiniLM.
- Notebook execution:
  - executed successfully with no cell errors.
  - MiniLM sample embedding dimension: 384.
  - MPNet sample embedding dimension: 768.
- Latency on the 10k sample:
  - MiniLM end-to-end average: 8.128 ms.
  - MPNet end-to-end average: 13.232 ms.
  - BM25 end-to-end average: 8.641 ms.
  - MiniLM FAISS-only average: 0.196 ms.
  - MPNet FAISS-only average: 0.379 ms.
- Graded proxy relevance results:

| Method | Precision@5 | NDCG@5 | MRR |
| --- | ---: | ---: | ---: |
| BM25 | 0.82 | 0.858 | 0.90 |
| MPNet | 0.84 | 0.781 | 0.90 |
| MiniLM | 0.82 | 0.730 | 0.90 |

- Test suite:
  - Week 5 tests passed: 7 passed.
  - Full project test suite passed: 219 passed, 1 skipped.

## Notes

- The Week 5 relevance evaluation is still a proxy evaluation, not a human-labeled benchmark.
- Query labels were changed from flat keyword lists to graded `core`, `related`, and `supporting` clue groups to reduce overly narrow keyword matching.
- Precision@5 and MRR treat grades 2 and 3 as clearly relevant.
- NDCG@5 uses the full 0-3 graded relevance score.
- Model and index artifacts are kept local because they are generated and relatively large.
