# Week 11 Product Integration Demo Report

## Overview

This week turned the REST API into a complete local product demo. The Streamlit interface exposes the three retrieval profiles, displays search results and original listing details, and records privacy-preserving usage metrics through the API.

## Product Demo

- Built a Streamlit search workspace on top of the Week 10 API. A natural-language request returns compliance-screened listings with public facts, a generated summary, matched preferences, and batch-loaded original listing descriptions.
- Added three product-facing search profiles: `fast` for BM25-only retrieval, `balanced` for Hybrid RRF retrieval, and `quality` for Hybrid RRF plus Cross Encoder reranking.
- Added optional same-query profile comparison. The client sends the three profile requests concurrently so the user can inspect retrieval differences without changing the query.
- Added a 1-100 result control, ten-result pages, relevance and price sorting, and a compact parsed-query display that separates explicit filters from preferences.
- Added listing-detail expansion backed by `POST /listings/details`. The detail view shows the listing ID, trusted structured facts, unmatched preferences when available, and the original listing remark.
- Added a small helpful/not-helpful feedback control after each search result set.

## Metrics and Evaluation

- Added anonymous demo event collection for searches and feedback. Events retain session IDs, selected profile, latency, result count, comparison usage, and feedback only; raw queries and listing text are not stored.
- Added a Metrics view with query volume, unique sessions, zero-result rate, profile usage, satisfaction proxy, and client/API P50, P90, and P95 latency overall and by search profile.
- Added `notebooks/11_product_integration_evaluation.ipynb` for live API validation. It checks active-snapshot compatibility, benchmarks all profiles, reports held-out relevance metrics, verifies hard-filter integrity, separates cache hits from misses, exercises batch details retrieval, and reads the runtime metrics endpoint without adding telemetry.

## Current Artifacts

- `demo/app.py`
  - Streamlit search and metrics workspace.

- `demo/api_client.py`
  - Small API client with concurrent same-query profile comparison and batch-detail retrieval.

- `demo/presentation.py`
  - Presentation helpers for public listing fields and parsed-query labels.

- `src/real_estate_nlp/api/demo_metrics.py`
  - Privacy-preserving aggregation for demo usage and latency metrics.

- `notebooks/11_product_integration_evaluation.ipynb`
  - API-level product evaluation and representative result review.

- `tests/test_demo_metrics.py` and `tests/test_demo_presentation.py`
  - Focused checks for metrics aggregation and UI presentation helpers.

## Validation

- Verified the complete local flow through Docker Compose: Streamlit UI, FastAPI, Redis, MySQL, the active search snapshot, and all three search profiles.
- Checked search submission, comparison mode, paging, listing details, feedback submission, and the metrics view against the running API.
- Confirmed that `/listings/details` supplies the original listing description and that the UI resets per-search paging and detail state.
- Full test suite passed: `350 passed, 1 skipped`.
- The Week 11 notebook was validated as a readable, executable notebook with nine compiled code cells. It is intended to run against the local API rather than store benchmark output in the repository.

## Notes

- The demo uses only API response fields intended for product display; retrieval traces, internal scores, and raw model artifacts remain private.
- Demo analytics are local Redis data with a seven-day TTL and a 10,000-event cap. Metrics are operational context, not a production analytics system.
- Search snapshots, models, raw MLS data, and original listing descriptions remain local artifacts under the repository's data-handling rules.
