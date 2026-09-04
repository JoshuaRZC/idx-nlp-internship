# Search Service Integration Report

## Overview

This milestone assembled the earlier NLP components into a pass-only listing search service and finalized its retrieval, reranking, and offline evaluation configuration before the API layer.

## Search Service Integration

- Built a versioned snapshot from the full `rets_property` table: `53,122` source listings, `53,091` `pass` listings, and `52,763` listings with usable text.
- Moved Fair Housing screening to the offline build path. Only `pass` listings enter the public catalog, dense index, BM25 artifact, signal index, and summary artifact; a query never reruns compliance checks.
- Added MySQL-backed hard eligibility for city, price, beds, baths, and square footage. The database candidate set is intersected with the snapshot's `pass` IDs before retrieval. County remains parsed context only.
- Set the public default to Hybrid + Cross Encoder retrieval: dense semantic candidates, BM25 candidates, and canonical signal matches are unioned, fused with RRF plus a fixed match-strength signal boost, then reranked within a bounded candidate window.
- Used signals as ranking evidence rather than broad SQL filters. Negative signals apply a small penalty; generic pool and view requests resolve to supported specific values.
- Separated price sorting into two contracts. Pure price requests use only structured eligibility and a stable price/listing-ID order. Price requests with positive preferences use complete signal matches, partial matches, semantic/lexical fallback, then remaining eligible listings.
- Selected `cross-encoder/ms-marco-MiniLM-L6-v2` as the default reranker after development evaluation. It reranks only the top 50 Hybrid candidates and records pre/post ranks, source evidence, and model scores for review. A reranker failure degrades to the RRF order rather than failing the request.
- Enabled two-worker parallel retrieval for the independent dense, BM25, and signal work after hard filtering. The configuration preserved ranking results while reducing local end-to-end latency relative to the serial path.

## Current Artifacts

- `src/real_estate_nlp/search_snapshot.py`: builds, validates, and activates coherent pass-only snapshots.
- `src/real_estate_nlp/listing_repository.py`: executes parameterized structured eligibility queries.
- `src/real_estate_nlp/search_service.py`: coordinates parsing, filtering, retrieval, fusion, price sorting, fallback, default bounded reranking, and degradation handling.
- `src/real_estate_nlp/signal_search.py`: provides inverted-index retrieval over normalized text signals.
- `scripts/build_search_snapshot.py`: builds an active snapshot from MySQL.
- `scripts/evaluate_search_relevance.py`: evaluates frozen development or test splits with Precision@5, NDCG@5, MRR@5, component timings, and degradation rate.
- `notebooks/10_search_service_evaluation.ipynb`: profiles the snapshot, compares retrieval variants and rerank windows, reviews errors, compares serial and parallel retrieval, and records the frozen final test result.

## Evaluation and Final Configuration

- Active snapshot: `53,122` source listings, `53,091` pass listings, and `52,763` text-retrievable listings.
- Default configuration: MiniLM dense retrieval, BM25, canonical signals, RRF `k=60`, up to 100 dense candidates, 100 BM25 candidates, 200 signal candidates, Cross Encoder reranking of the top 50 candidates, and two retrieval workers.
- Controlled serial development comparison: Hybrid RRF reached Precision@5 `0.843`, NDCG@5 `0.808`, and MRR@5 `0.976`; adding the selected Cross Encoder reached `0.907`, `0.877`, and `0.964` respectively. The reranker improved graded top-five quality, while the RRF order retained a slightly earlier first relevant result on this small dev set.
- The final test used the default parallel configuration on 12 held-out queries. The frozen 849-label qrels file produced Precision@5 `0.867`, NDCG@5 `0.901`, and MRR@5 `0.917`, with local P50/P95 total latency of `279.58 ms` / `535.72 ms`.
- Returned but previously unjudged test candidates were labeled in a blinded delta pool before the final scored run. No retrieval or reranking setting was changed after the test manifest was frozen.

## Validation

- Snapshot validation checks checksums, artifact presence, pass-only publication, ID alignment, and record counts before activation.
- The notebook completed against the active local snapshot and covers relevance, pure-price, soft-preference price, component, rerank-window, serial/parallel, development, and final-test views.
- `tests/test_search_service.py` covers pass-only publication, parameterized SQL, candidate restriction, signal hierarchy, RRF behavior, price tiers, degradation, fallback, Cross Encoder traces, and warm-up behavior.
- Full test suite passed: `328 passed, 1 skipped`.

## Notes

- Search snapshots, indexes, and MLS-derived artifacts remain local under `data/models/`.
- The reported latency is a local, warmed-snapshot measurement rather than a production SLA. API contracts, pagination, caching, and production observability remain subsequent work.
