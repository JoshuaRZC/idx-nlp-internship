# Week 7 Report

## Overview

This week focused on language-based search query intent classification. The work added a labeled query dataset, a calibrated logistic-regression classifier, development-based refinement, independent final evaluation, and optional integration with the Week 4 query parser.

## Week 7 Query Intent Classification

- Defined three language-level labels: `browsing`, `researching`, and `high_intent_inquiry`.
- Built a curated dataset of 504 manually authored real-estate queries, balanced at 168 examples per label.
- Used 360 training queries, 72 development queries, and 72 independent final-test queries. Expression families do not cross split boundaries.
- Added contrastive training examples that separate casual phrases such as `I want to browse` and `can I see listings` from explicit actions such as touring, booking, contacting an agent, or making an offer.
- Normalized known city names before vectorization so location frequency cannot act as an intent shortcut.
- Implemented `QueryIntentClassifier` with TF-IDF word and phrase features, logistic regression, and five-fold sigmoid probability calibration.
- Added `confidence` and `is_uncertain` to each prediction. The uncertainty flag uses a 0.60 threshold without creating a fourth label.
- Integrated the classifier with `QueryParser` as an optional dependency. Parser task intent remains separate from the new `language_intent` output.

## Current Artifacts

- `data/processed/query_intent_labels.json`
  - Versioned, non-sensitive training, development, and final evaluation data for Week 7.

- `src/real_estate_nlp/query_intent_classifier.py`
  - Trains, predicts, saves, and loads the calibrated classifier.

- `scripts/train_query_intent_classifier.py`
  - Trains from the fixed training split and writes local model artifacts.

- `scripts/evaluate_query_intent_classifier.py`
  - Evaluates the saved model against the fixed test split.

- `notebooks/07_query_intent_classification.ipynb`
  - Reviews label composition, held-out metrics, confidence behavior, errors, and parser integration.

- `tests/test_week7.py`
  - Validates dataset balance and split isolation, classifier behavior, model persistence, evaluation output, and optional parser integration.

## Validation

- Development evaluation used 72 queries to select the final configuration: accuracy `0.986` and browsing recall `0.958`.
- Final evaluation used 72 separate queries that were not used for fitting, calibration, or refinement: accuracy `0.958`, exceeding the Week 7 target of 80%.
- Final per-label F1: browsing `0.933`, researching `1.000`, high-intent inquiry `0.941`.
- All three remaining final-test errors have confidence below `0.60`, supporting the use of the uncertainty flag for review-sensitive flows.
- The Week 7 notebook executed with no cell errors.

## Notes

- The classifier infers intent from query wording only. It is not a buyer-scoring, conversion, or CRM model.
- Specific filters or a first-person request alone do not imply high intent. High-intent labels require language indicating action, timing, availability, or transaction readiness.
- The trained model and evaluation JSON are generated local artifacts under `data/models/` and `data/processed/`; the curated labels remain versioned for reproducibility.
