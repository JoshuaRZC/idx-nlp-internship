# Search Relevance Annotation Rules

## Purpose

This rule defines manual relevance labels for the pass-only Search Service benchmark. Judge each listing from the query, the displayed structured fields, and `remarks_cleaned`. Do not use result rank, model score, summary, extracted signals, or candidate source.

The benchmark is tied to one snapshot. A label is valid only for the `snapshot_id` shown in its annotation row.

## Grade Scale

| Grade | Meaning |
| --- | --- |
| `3` | Meets every hard requirement and has direct evidence for all primary preferences. |
| `2` | Meets hard requirements and is clearly relevant, but only partially satisfies multiple primary preferences or has a weaker equivalent. |
| `1` | Meets hard requirements but has only broad or weak topical relevance. |
| `0` | Misses a hard requirement, contradicts a requested feature, or is not relevant. |

Hard requirements use the displayed structured fields. Free-text preferences require direct evidence in `remarks_cleaned`; do not infer nearby locations, amenity availability, condition, or property type from generic marketing language.

For a conjunction such as "private pool and fireplace," a listing with only one explicit feature is usually `2`; both features need direct evidence for `3`. A community pool is not evidence of a requested private pool. A generic view is not evidence of a requested ocean view.

## Workflow

1. Review the query and its listings in the randomized annotation order.
2. Assign `relevance_grade`, write a short factual rationale, and set `annotation_status` to `complete`.
3. Do not alter `query_id`, `listing_id`, `snapshot_id`, or displayed listing fields.
4. Complete a small calibration batch first. Revisit disputed grade boundaries before labeling the remaining pool.
5. Re-review a random 15% of completed rows without looking at their previous grades. Resolve differences before copying the final rows to the qrels file.

The benchmark reports Precision@5 and MRR@5 using grades `2` and `3` as relevant. NDCG@5 uses the full `0` through `3` scale.
