# Search Relevance Dev Experiment

## Evaluation Boundary

- Snapshot: `20260903T124929Z_5466f5d6de`
- Development set: 28 manually judged queries
- Test set: 12 manually judged queries, frozen and not used here
- Relevance threshold for Precision@5 and MRR@5: grade >= 2
- NDCG@5 uses the full 0-3 relevance scale

The query dataset and `817` qrels are protected by
`search_relevance_rerank_window_manifest.json`. An evaluation run fails if
either file or the active snapshot differs from the frozen manifest.

## Dev Results

| Variant | P@5 | NDCG@5 | MRR@5 | P50 latency | P95 latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.721 | 0.605 | 0.836 | 62 ms | 208 ms |
| Dense | 0.586 | 0.499 | 0.815 | 91 ms | 142 ms |
| Dense + signals | 0.800 | 0.718 | 0.914 | 83 ms | 206 ms |
| Dense + BM25 + signals RRF | 0.843 | 0.808 | **0.976** | 130 ms | 404 ms |
| RRF + cross-encoder, window 50 | **0.907** | **0.877** | 0.964 | 307 ms | 617 ms |

## Decision

`hybrid_cross_encoder` is the default relevance strategy. The document now
includes structured facts, the original remark, extracted signals, and the
compact summary. With a rerank window of 50, it gives the strongest P@5 and
NDCG@5 result while keeping lower latency than a window of 100. If model
reranking is unavailable, the service preserves the Hybrid RRF order and marks
the response as degraded.

## Rerank Window

| Window | P@5 | NDCG@5 | MRR@5 | P50 latency | P95 latency |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 0.871 | 0.842 | **0.982** | 202 ms | 520 ms |
| 50 | **0.907** | **0.877** | 0.964 | 283 ms | 584 ms |
| 100 | 0.893 | 0.872 | 0.946 | 442 ms | 687 ms |

Smaller-window candidates were blinded and labeled before this comparison. The
window changes only the number of RRF candidates sent to the Cross Encoder; it
does not change the upstream retrieval sources.

## Cross-Encoder Review

The largest losses from the earlier document representation were checked against
the blinded remarks and their manual grades. The labels were retained. The old
representation preferred a compact listing summary over the full remark, which
could omit material constraints or negation:

- `rel_024`: proposed ADUs were ranked above properties with an existing ADU
  and a separate entrance.
- `rel_011`: two-story pool homes were promoted because the summary omitted the
  floor count.
- `rel_002`: a decorative-only fireplace was promoted because that qualifier was
  absent from the summary.
- `rel_018`: the city name `Mountain View` was treated as a mountain-view
  feature.

The updated document combines structured facts, original remarks, signals, and
the summary. The resulting comparison expanded the qrels only when a new
window surfaced previously unjudged top-five candidates.

Reproduce the dev run with:

```bash
conda run -n idx-nlp python -m scripts.evaluate_search_relevance \
  --qrels data/processed/search_relevance_rerank_window_qrels.jsonl \
  --manifest data/processed/search_relevance_rerank_window_manifest.json \
  --output data/processed/search_relevance_default_cross_encoder_dev_results.json \
  --splits dev
```

Run the frozen test set only after a future change warrants a final comparison:

```bash
conda run -n idx-nlp python -m scripts.evaluate_search_relevance \
  --qrels data/processed/search_relevance_rerank_window_qrels.jsonl \
  --manifest data/processed/search_relevance_rerank_window_manifest.json \
  --output data/processed/search_relevance_test_results.json \
  --splits test
```
