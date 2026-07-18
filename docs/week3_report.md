# Week 3 Report

## Overview

This week focused on named entity extraction for real estate listing remarks. The main work was to build a rule-based `EntityExtractor`, prepare reviewed span labels, evaluate extraction quality, and use error analysis to improve the rule baseline.

## Week 3 Entity Extraction

- Built an `EntityExtractor` class for structured listing entities.
- Added regex extraction for numeric and structured fields:
  - `bedrooms`: bedroom counts and selected ordinal bedroom phrasing.
  - `bathrooms`: decimal, half-bath, and written fraction patterns.
  - `price`: listing price mentions.
  - `sqft`: living area square footage.
  - `lot_size`: acre, square-foot lot, and lot-dimension patterns.
  - `year_built`: build-year mentions.
  - `stories`: story counts and split-level references.
  - `parking`: garage, carport, and parking-count patterns.
  - `hoa_fee`: monthly HOA and no-HOA mentions.
- Added taxonomy-based extraction for broader real estate language, including amenities, rooms, condition terms, property types, transaction terms, location features, and interior/exterior features.
- Added rule-based phrase mappings for common listing expressions such as `open concept living`, `abundant natural light`, `roof top deck`, `fenced backyard`, `rv access`, and `brand new flooring`.
- Added context filters to reduce false positives from ambiguous terms such as `kitchen`, `garage`, `lease`, `beach`, `living areas`, and `cabinets`.
- Kept a NER interface in the extractor so a callable model or object with `extract(text)` can be plugged in later.

## Evaluation Dataset and NER Experiment

- Created reviewed span-label datasets for entity extraction.
- Used a held-out evaluation set of 200 listing remarks with 2,619 labeled entities.
- Trained and retained one small spaCy NER model as an experimental comparison point.
- Compared three extraction paths:
  - rule-based extractor
  - saved NER model
  - hybrid extractor combining rules and NER output
- Kept the rule-based extractor as the main path because it was more predictable on numeric facts, taxonomy terms, and normalized values.

## Current Artifacts

- `scripts/entity_extractor.py`
  - Contains the rule-based extractor, taxonomy matching, phrase rules, conflict handling, and NER interface.

- `scripts/evaluate_entities.py`
  - Evaluates entity predictions with precision, recall, and F1.
  - Supports strict, overlap, value, and span-style matching.

- `scripts/train_ner.py`
  - Trains the saved spaCy NER experiment model.

- `data/processed/entity_train_labels.json`
  - 640 reviewed training examples.
  - 13,855 labeled entities.

- `data/processed/entity_dev_labels.json`
  - 160 reviewed development examples.
  - 3,568 labeled entities.

- `data/processed/entity_eval_labels.json`
  - 200 reviewed evaluation examples.
  - 2,619 labeled entities.

- `data/models/entity_ner/`
  - Saved spaCy NER experiment model.
  - Current local size is about 3.9 MB.

- `notebooks/03_entity_extraction_evaluation.ipynb`
  - Compares rule, NER, and hybrid extraction.
  - Includes per-label scores, examples, and error analysis.

- `tests/test_week3.py`
  - Validates entity extraction behavior, schema, spans, taxonomy matching, NER interface, and edge cases.

## Validation

- Rule extractor on held-out evaluation set:
  - strict: P=0.889, R=0.814, F1=0.850.
  - overlap: P=0.916, R=0.839, F1=0.876.
  - value: P=0.925, R=0.848, F1=0.885.
- Saved NER model on held-out evaluation set:
  - span: P=0.822, R=0.727, F1=0.772.
- Hybrid extractor on held-out evaluation set:
  - span: P=0.877, R=0.831, F1=0.853.
- Week 3 entity tests passed: 50 passed.

## Notes

- The rule-based extractor met the 85% F1 target under strict matching.
- Strict scoring remains sensitive to span boundaries and label-value choices, especially for broad categories such as `room`, `location`, and `amenity`.
- Overlap and value-based scores are higher, which suggests many remaining errors are boundary or annotation-granularity issues rather than fully incorrect entity detection.
- The NER path was useful as a benchmark, but the current project direction remains rule-based because it is easier to inspect, tune, and explain.
- Reviewed label files and generated model artifacts are local project assets; raw listing data remains excluded from Git.
