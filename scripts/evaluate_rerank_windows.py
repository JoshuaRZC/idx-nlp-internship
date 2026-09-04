"""Compare Cross Encoder rerank windows against frozen relevance labels."""

import argparse
import json
from pathlib import Path

from scripts.evaluate_search_relevance import (
    evaluate_items,
    load_manifest,
    load_qrels,
    load_query_dataset,
    validate_manifest,
)
from src.real_estate_nlp.search_service import SearchService


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Cross Encoder rerank windows.")
    parser.add_argument("--queries", default="data/processed/search_relevance_queries.json")
    parser.add_argument("--qrels", default="data/processed/search_relevance_qrels_expanded.jsonl")
    parser.add_argument("--manifest", default="data/processed/search_relevance_expanded_manifest.json")
    parser.add_argument("--output", default="data/processed/search_relevance_rerank_window_dev_results.json")
    parser.add_argument("--search-root", default="data/models/search")
    parser.add_argument("--windows", type=int, nargs="+", default=(20, 50, 100))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--splits", choices=("dev", "test"), nargs="+", default=("dev",))
    return parser.parse_args()


def evaluate_windows(service, query_dataset, qrels, windows, top_k, splits):
    results = {}
    for window in windows:
        if window < top_k:
            raise ValueError("Each rerank window must be at least top_k.")
        service.rerank_k = window
        report = evaluate_items(
            service,
            query_dataset,
            qrels,
            top_k=top_k,
            variants=("hybrid_cross_encoder",),
            splits=splits,
        )
        results[str(window)] = report["variants"]["hybrid_cross_encoder"]
    return results


def main():
    args = parse_args()
    query_dataset = load_query_dataset(args.queries)
    qrels = load_qrels(args.qrels)
    service = SearchService.from_active_snapshot(
        search_root=args.search_root,
        enable_cross_encoder=True,
    )
    service.warm_up(include_cross_encoder=True)
    validate_manifest(load_manifest(args.manifest), args.queries, args.qrels, service.snapshot.snapshot_id)

    results = evaluate_windows(
        service,
        query_dataset,
        qrels,
        args.windows,
        args.top_k,
        args.splits,
    )
    payload = {
        "snapshot_id": service.snapshot.snapshot_id,
        "top_k": args.top_k,
        "splits": list(args.splits),
        "windows": results,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for window, values in results.items():
        for split, metrics in values.items():
            print(
                f"window={window} [{split}] "
                f"P@5={metrics['precision_at_5']:.3f} "
                f"NDCG@5={metrics['ndcg_at_5']:.3f} "
                f"MRR@5={metrics['mrr_at_5']:.3f} "
                f"P50={metrics['latency_ms'].get('p50', 0):.1f}ms "
                f"P95={metrics['latency_ms'].get('p95', 0):.1f}ms"
            )
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
