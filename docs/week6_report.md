# Week 6 Report

## Overview

This week focused on converting remark-level extraction into listing-level signals. The work moved reusable NLP components into the package layer, built a `SignalExtractor` over full listing records, generated a compact JSONL artifact for the complete `rets_property` table, and evaluated the result against reviewed real listings.

## Week 6 Listing Signal Extraction

- Moved the reusable `TextCleaner` and `EntityExtractor` implementations into `src/real_estate_nlp/`.
- Updated scripts and notebooks to import reusable components directly from `src/real_estate_nlp/`.
- Built a `SignalExtractor` that processes complete listing records instead of only free-text remarks.
- Combined three signal sources:
  - structured MLS fields such as city, price, beds, baths, and square feet.
  - Week 3 entity extraction over cleaned remarks.
  - extra phrase rules for financing, condition, location, amenity, transaction, and investment signals.
- Designed a compact listing-level JSON schema with `listing_id`, grouped `text_signals`, `numeric_signals`, and flattened `keywords`.
- Kept the output focused on product-facing fields; source metadata, entity spans, and extraction evidence are not stored in the final artifact.
- Added canonical value mapping so broad or inconsistent text values become more useful search signals, such as `shopping` to `near shopping` and `dining` to `near dining`.
- Added a batch extraction script that can run against either MySQL or a local CSV sample.
- Ran the MySQL path over the complete `rets_property` table and generated the final local artifact.

## Current Artifacts

- `src/real_estate_nlp/text_cleaner.py`
  - Package-level Week 2 text cleaner.

- `src/real_estate_nlp/entity_extractor.py`
  - Package-level Week 3 entity extractor.

- `src/real_estate_nlp/signal_extractor.py`
  - Converts full listing records into listing-level search/filtering signals.

- `scripts/extract_listing_signals.py`
  - Reads listing records from MySQL or CSV and writes JSONL output.
  - MySQL runs write `data/processed/listing_signals.jsonl`; CSV input can be used for a smaller local run.

- `data/processed/listing_signals.jsonl`
  - Local generated signal output for the complete `rets_property` table.
  - Contains 53,122 listing-level records.
  - Ignored by Git.

- `data/processed/listing_signal_eval_labels.json`
  - Local reviewed evaluation set of 200 real listings.
  - Ignored by Git with the source records and evaluation results.

- `notebooks/06_listing_signal_extraction.ipynb`
  - Reviews schema, signal coverage, common signal values, listing examples, and light error analysis.

- `tests/test_week6.py`
  - Validates schema, entity-to-signal mapping, deduplication, empty text handling, MLS field aliases, financing rules, transaction routing, and batch helper behavior.

- `tests/test_listing_signal_evaluation.py`
  - Validates the evaluation schema and metric calculations.

## Validation

- Full test suite passed: 237 passed, 1 skipped.
- Full MySQL extraction completed successfully:
  - 53,122 listing signal records generated.
  - Core MLS fields have near-complete coverage: price 100.0%, beds 99.8%, baths 100.0%, and square footage 99.9%.
  - Interior, exterior, and location signal coverage is 83.9%, 78.4%, and 76.0%, respectively.
- Evaluation on 200 reviewed real listings met the Week 6 targets:
  - structured field accuracy: 1.000.
  - free-text F1: 0.799.
  - keyword integrity: 1.000.
- Week 6 notebook executed successfully with no cell errors.

## Notes

- Structured numeric signals prefer trusted MLS fields when available and use text extraction only to fill gaps.
- Free-text signals are grouped for retrieval and ranking, not necessarily hard SQL filtering.
- Some broad signals, especially location-style terms, should remain soft ranking features unless later evaluation shows they are safe as filters.
