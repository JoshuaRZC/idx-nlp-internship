# Week 1 Report

## Overview

This week focused on setting up the local development workflow and building the first NLP assets for real estate listing text: a listing sample, a domain taxonomy, and labeled search-query examples.

## Week 0 Setup

- Set up the project repository structure for the NLP track.
- Configured Python 3.11 with the required project dependencies.
- Added a local MySQL service through Docker Compose.
- Loaded MLS SQL files locally into the `real_estate` database.
- Verified the environment with setup tests.
- Updated `.gitignore` so raw MLS data, local instructions, and generated intermediate files are not committed.

## Week 1 Taxonomy

- Extracted a sample of 1,000 listing records from `rets_property`.
- Used `L_Remarks` as the main text field for taxonomy and NLP preparation.
- Generated a taxonomy seed from listing remarks using n-gram frequency analysis.
- Cleaned and expanded the taxonomy into 304 real estate terms across 8 categories.
- Converted the cleaned taxonomy CSV into `taxonomy.json`.
- Created 120 labeled sample user queries for future query parsing and intent classification.
- Added simple, medium, and hard query examples to better reflect real user search behavior.
- Created an exploration notebook to review listing fields, remark patterns, taxonomy coverage, and query coverage.
- Added Week 1 validation tests for sample data, taxonomy structure, query labels, and taxonomy coverage.

## Current Artifacts

- `data/processed/listing_sample.csv`
  - 1,000 local listing samples.

- `data/processed/taxonomy.json`
  - 304 terms.
  - 8 categories.

- `data/processed/sample_queries.json`
  - 120 labeled user queries.
  - Includes intent, entities, and difficulty.

- `scripts/data_loading.py`
  - Extracts listing samples from MySQL.

- `scripts/taxonomy_builder.py`
  - Generates taxonomy seed terms from listing remarks.

- `scripts/taxonomy_csv_to_json.py`
  - Converts the cleaned taxonomy CSV into JSON.

- `notebooks/01_remark_exploration.ipynb`
  - Explores the Week 1 listing sample, taxonomy, and query set.

- `tests/test_week1.py`
  - Validates Week 1 deliverables.

## Validation

- Listing sample contains at least 500 records.
- Remarks are non-empty and longer than the minimum required length.
- Taxonomy contains more than 200 terms.
- Taxonomy covers 8 categories.
- Sample query set contains more than 50 labeled queries.
- Query labels include multiple intents and difficulty levels.
- Taxonomy coverage over the sample listing remarks meets the Week 1 target.

## Notes

- `listing_sample.csv`, taxonomy seed files, raw SQL files, and local instructions remain ignored by Git.
- `taxonomy.json` and `sample_queries.json` are allowed for GitHub submission because they are curated project assets, not raw MLS data.
