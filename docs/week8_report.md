# Week 8 Report

## Overview

This week focused on converting complete listing records into concise, factual summaries for search results and alert-style surfaces. The work combined trusted MLS fields with Week 6 text signals, added a frozen evaluation workflow, and introduced a small answerability layer for the listing-search path.

## Week 8 Listing Summarization

- Added `ListingSummarizer` with both extractive sentence selection and a product-facing hybrid summary method.
- Used MLS price, beds, baths, and city as the factual summary frame; remark-derived signals only supply feature detail.
- Applied a deterministic feature policy that favors distinctive views, pool, solar, ADU, outdoor features, and material interior improvements while avoiding financing and transaction terms as highlights.
- Treated zero beds or baths as missing values for summary text, which avoids presenting land or non-residential records as zero-bedroom homes.
- Generated `listing_summaries.jsonl` for all 53,122 records in `rets_property`.
- Built an independent `AnswerabilityChecker` around the Week 4 parser and schema validator.
  - It distinguishes listing searches from out-of-domain or knowledge-style requests before execution.
  - It explains empty and all-null result sets after execution.
- Created a frozen 50-listing real-data evaluation set: 20 development listings and 30 final-test listings.
- Audited up to two source-grounded key features per listing directly from the original remarks.

## Current Artifacts

- `src/real_estate_nlp/listing_summarizer.py`
  - Extractive sentence scoring and structured-field-first hybrid summaries.

- `src/real_estate_nlp/answerability_checker.py`
  - Pre-query and post-query listing-search checks with user-facing messages.

- `scripts/generate_listing_summaries.py`
  - Loads complete listing records and Week 6 signals, then writes full-table summaries.

- `scripts/select_listing_summary_eval_sample.py`
  - Selects the fixed 50-listing evaluation source from real MLS records.

- `scripts/build_listing_summary_eval_labels.py`
  - Builds the local label schema for independent reference summaries and fact checks.

- `scripts/evaluate_listing_summaries.py`
  - Reports ROUGE-L and combined fact coverage.

- `scripts/prepare_listing_summary_self_review.py`
  - Exports 20 fixed final-test listings for local review.

- `notebooks/08_listing_summarization.ipynb`
  - Reviews sample composition, automatic metrics, examples, and the self-review sheet.

## Validation

- Development evaluation on 20 listings: ROUGE-L `0.464`, fact coverage `0.815`.
- Final evaluation on 30 listings: ROUGE-L `0.457`, fact coverage `0.733`. ROUGE-L exceeds the handbook target of `0.40`.
- Full-table generation wrote 53,122 local summary records.
- `tests/test_week8.py` covers summary construction, field precedence, feature diversity, extractive ordering, fallback behavior, batch output, evaluation, and answerability checks.
- Full test suite passed: `258 passed, 1 skipped`.

## Notes

- Each evaluation label contains a reference summary, trusted MLS facts, and up to two manually selected `feature_gold` terms.
- BART/T5 abstractive generation remains out of scope. The current hybrid approach is easier to audit and does not introduce generation-time factual claims.
