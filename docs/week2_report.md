# Week 2 Report

## Overview

This week focused on building a text cleaning and normalization pipeline for real estate listing remarks. The goal was to reduce noisy MLS language into more consistent text while preserving the numeric and domain-specific details needed for later entity extraction.

## Week 2 Text Cleaning

- Built a `TextCleaner` class for listing remark normalization.
- Added 11 normalization methods:
  - `normalize_unicode`: standardizes quotes, dashes, and spacing.
  - `remove_html`: removes tags and decodes HTML entities.
  - `normalize_case`: lowercases text.
  - `normalize_prices`: converts price shorthand.
  - `normalize_measurements`: standardizes square footage, acres, and lot dimensions.
  - `normalize_bed_bath_counts`: standardizes bed and bath counts.
  - `normalize_parking`: standardizes garage and parking language.
  - `normalize_hoa`: standardizes HOA mentions and fees.
  - `normalize_year_built`: standardizes build-year phrases.
  - `normalize_stories`: standardizes story and level descriptions.
  - `normalize_punctuation`: cleans punctuation and separators.
- Expanded the abbreviation dictionary to 182 real estate and MLS-style mappings, such as `br -> bedroom`, `ba -> bathroom`, `sqft -> square feet`, `w/ -> with`, `hoa -> homeowners association`, and `ss -> stainless steel`.
- Kept ambiguous address terms conservative, including leaving `Dr` and `St` unexpanded to avoid corrupting addresses.
- Added a cleaned dataset generation script that reads the Week 1 listing sample and writes a cleaned version with `remarks_cleaned`.
- Generated a cleaned listing sample with 1,000 rows.
- Created a Week 2 notebook to profile the raw dataset, review the cleaned dataset, and compare before/after remark examples.
- Added Week 2 tests covering edge cases across the cleaning pipeline.

## Current Artifacts

- `scripts/text_cleaning.py`
  - Contains the `TextCleaner` class and normalization methods.
  - Includes the abbreviation dictionary and profiling helper.

- `scripts/generate_cleaned_dataset.py`
  - Generates `data/processed/listing_sample_cleaned.csv` from the Week 1 listing sample.

- `data/processed/listing_sample_cleaned.csv`
  - Local cleaned dataset with 1,000 rows.
  - Adds `remarks_cleaned` while retaining the original `remarks`.

- `notebooks/02_text_cleaning_exploration.ipynb`
  - Profiles raw remarks, checks cleaned output, and shows before/after examples.

- `tests/test_week2.py`
  - Validates Week 2 text cleaning behavior.

## Validation

- `TextCleaner` includes more than 6 normalization methods.
- Abbreviation dictionary includes more than 30 mappings.
- Cleaned dataset contains 1,000 rows, matching the Week 1 listing sample.
- Cleaned dataset keeps both original and cleaned remarks for review.
- Week 2 test suite includes more than 40 test cases.
- Week 2 tests passed: 74 passed.

## Notes

- The cleaned dataset remains ignored by Git as a generated local data artifact.
