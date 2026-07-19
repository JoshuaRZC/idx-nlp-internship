# Week 4 Report

## Overview

This week focused on converting natural-language property search requests into structured filters and safe SQL clauses. The main work was to build a `QueryParser`, separate hard SQL filters from soft search signals, add schema validation, and evaluate parser behavior against the Week 1 sample query set.

## Week 4 Query Parser

- Built a rule-based `QueryParser` for real estate search queries.
- Added parsing support for structured hard filters:
  - `city`: known city matching.
  - `county`: supported county aliases.
  - `price_min` / `price_max`: price floors, caps, and ranges.
  - `beds` / `beds_min` / `beds_max`: bedroom counts and minimums.
  - `baths` / `baths_min` / `baths_max`: bathroom counts and minimums.
  - `sqft` / `sqft_min` / `sqft_max`: square-foot exact values, minimums, maximums, and ranges.
  - `private_pool`, `fireplace`, and `has_view`: structured database-backed feature flags.
- Added soft-signal parsing for amenities, property types, rooms, condition terms, interior and exterior features, location features, investment language, transaction preferences, and summary requests.
- Split parser output into:
  - `hard_filters`: safe to use as SQL WHERE conditions.
  - `soft_signals`: useful for ranking, semantic search, or result explanation.
- Added context filters to reduce false positives from broad terms such as `beach`, `house`, `private`, `rental`, `upside`, and `family`.
- Replaced the small hardcoded city list with a reusable city-list asset generated from `rets_property.L_City`.
- Added a parameterized SQL generator that keeps user-derived values in the params list instead of interpolating them into SQL strings.
- Added optional SQL inclusion for soft signals through `L_Remarks LIKE` clauses when explicitly requested.

## Schema Validation

- Built a `SchemaValidator` for parser output.
- Added validation for unsupported filter keys, unknown cities, price ranges, bed and bath ranges, square-foot ranges, boolean feature flags, list-style soft fields, and inverted ranges.
- Profiled the full local `rets_property` table and kept conservative numeric validation bounds instead of using raw min/max values with outliers.

## Current Artifacts

- `src/real_estate_nlp/query_parser.py`
  - Contains the Week 4 query parser, hard/soft filter split, parameterized SQL generation, phrase rules, and context filters.

- `src/real_estate_nlp/schema_validator.py`
  - Validates structured parser output before SQL generation or downstream use.

- `scripts/evaluate_query_parser.py`
  - Evaluates parser output against `data/processed/sample_queries.json`.
  - Reports hard-filter, soft-signal, and full-filter exact match rates.

- `scripts/generate_city_list.py`
  - Generates the reusable city-list asset from the local MySQL database.

- `data/processed/valid_cities.json`
  - Contains 966 parser-ready cities from `rets_property.L_City`.
  - Blocks a small set of ambiguous or non-city values such as `Cool`, `Nice`, `Other`, `Unincorporated`, `Unknown`, and `Weed`.

- `notebooks/04_query_parser_evaluation.ipynb`
  - Reviews parser outputs, hard/soft filter behavior, evaluation metrics, SQL generation, validation examples, and error analysis.

- `tests/test_week4.py`
  - Validates query parsing, hard/soft splitting, SQL generation, SQL injection protection, schema validation, and evaluation behavior.

## Validation

- Week 4 parser evaluation on 120 labeled sample queries:
  - hard-filter exact match rate: 1.000.
  - soft-signal exact match rate: 1.000.
  - full-filter exact match rate: 0.917.
  - expected fields matched: 205 / 205.
- Full project test suite passed: 212 passed, 1 skipped.
- SQL injection tests confirm that user text remains parameterized and is not concatenated into SQL.
- Full database profiling checked 53,122 listings, 972 distinct city values, and the price, bed, bath, and square-foot distributions used to review validation bounds.
- Soft-signal error analysis was used to reduce duplicate and over-broad matches, especially around city names, property-type language, parking terms, and summary requests.

## Notes

- Hard filters represent fields that can safely constrain SQL results by default.
- Soft signals are intentionally kept separate so they do not over-filter search results.
- City matching now uses a generated local JSON asset, while numeric validation bounds remain conservative constants to avoid following extreme database outliers.
- The full-filter exact match rate remains below 1.000 because the parser now emits database-backed hard flags such as `private_pool`, `fireplace`, and `has_view`, while the original Week 1 labels did not always include those fields explicitly.
- The current parser is rule-based and inspectable, which makes it easier to tune and explain before adding semantic search or model-based ranking in later weeks.
