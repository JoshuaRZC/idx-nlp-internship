# Week 9 Report

## Overview

This week focused on Fair Housing compliance screening for listing remarks. The work added an explainable Federal rule baseline, a local evaluation workflow, and a submission-oriented publication decision contract.

## Week 9 Fair Housing Compliance

- Added `ComplianceChecker` with a versioned `federal-1.1` pattern library covering race, color, national origin, religion, sex, familial status, and disability.
- Used three finding severities: `error` blocks publication, `warning` requires reviewer confirmation, and `info` records policy-sensitive phrases without making a legal conclusion.
- Kept matching on the original remark so every finding includes the matched text and its source span.
- Built one local 264-item evaluation set: 204 synthetic policy examples and 60 manually reviewed neutral MLS remarks.
- The synthetic examples cover explicit violations, review-sensitive wording, paraphrases, longer remark contexts, multiple simultaneous findings, and neutral counterexamples.
- Added a CSV-to-JSONL batch checker and a Week 9 notebook for label composition, metrics, protected-class coverage, and error review.

## Current Artifacts

- `src/real_estate_nlp/compliance_checker.py`
  - Applies policy rules and returns `pass`, `review`, or `blocked` with audit-ready findings.

- `src/real_estate_nlp/compliance_rules.py`
  - Defines the Federal Fair Housing pattern library and stable rule IDs.

- `scripts/build_compliance_eval_labels.py`
  - Creates the local evaluation-label scaffold and requires an explicit review step for MLS-neutral candidates.

- `scripts/evaluate_compliance_checker.py`
  - Reports release-gate recall, alert precision, status accuracy, clean-listing false-positive rate, and protected-class recall.

- `docs/fair_housing_rules.md`
  - Documents rule scope, review outcomes, integration behavior, and policy maintenance.

## Validation

- After refining the pattern library against the full evaluation set, the 264-item evaluation reports known-violation recall `1.000`, actionable-alert precision `1.000`, status accuracy `1.000`, and clean-listing false-positive rate `0.000`.
- The `federal-1.1` update adds bounded paraphrase patterns and protects checked counterexamples for negated policy wording and `single-story` or `single-level` property descriptions.
- A local 10k MLS batch run produced `9,996 pass`, `4 review`, and `0 blocked` results. The review cases came from expected demographic or occupant-preference patterns.
- `tests/test_week9.py` covers explicit violations, neutral descriptions, warnings, info findings, source spans, overlap handling, batch output, and evaluation metrics.
- Full test suite passed: `295 passed, 1 skipped` under Python 3.11.15.

## Notes

- The checked-in policy is the Federal baseline only. California or local requirements should be added as a separately versioned policy extension.
- The local labels, evaluation results, and batch output remain ignored because they contain MLS remark text.
- A `pass` result means no configured rule matched; it is not a legal certification.
