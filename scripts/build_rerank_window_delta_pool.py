"""Build one blinded annotation pool for additional rerank-window candidates."""

import argparse
import random
from collections import defaultdict

from scripts.build_search_relevance_delta_pool import build_delta_pool
from scripts.build_search_relevance_pool import write_jsonl
from scripts.evaluate_search_relevance import (
    load_manifest,
    load_qrels,
    load_query_dataset,
    validate_manifest,
)
from src.real_estate_nlp.search_service import SearchService


def parse_args():
    parser = argparse.ArgumentParser(description="Build a blind delta pool for rerank-window experiments.")
    parser.add_argument("--queries", default="data/processed/search_relevance_queries.json")
    parser.add_argument("--qrels", default="data/processed/search_relevance_qrels_expanded.jsonl")
    parser.add_argument("--manifest", default="data/processed/search_relevance_expanded_manifest.json")
    parser.add_argument("--output", default="data/processed/search_relevance_rerank_window_delta_pool.jsonl")
    parser.add_argument("--search-root", default="data/models/search")
    parser.add_argument("--windows", type=int, nargs="+", default=(20, 50))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def combine_rows(rows, seed):
    by_query = defaultdict(dict)
    for row in rows:
        key = str(row["listing_id"])
        by_query[row["query_id"]].setdefault(key, row)

    combined = []
    for query_id, items in sorted(by_query.items()):
        query_rows = list(items.values())
        random.Random(f"{seed}:{query_id}").shuffle(query_rows)
        for annotation_order, row in enumerate(query_rows, start=1):
            row["annotation_order"] = annotation_order
        combined.extend(query_rows)
    return combined


def main():
    args = parse_args()
    if any(window < args.top_k for window in args.windows):
        raise ValueError("Each rerank window must be at least top_k.")

    query_dataset = load_query_dataset(args.queries)
    qrels = load_qrels(args.qrels)
    service = SearchService.from_active_snapshot(
        search_root=args.search_root,
        enable_cross_encoder=True,
    )
    service.warm_up(include_cross_encoder=True)
    validate_manifest(load_manifest(args.manifest), args.queries, args.qrels, service.snapshot.snapshot_id)

    rows = []
    for window in args.windows:
        service.rerank_k = window
        rows.extend(
            build_delta_pool(
                service,
                query_dataset,
                qrels,
                "hybrid_cross_encoder",
                split=args.split,
                top_k=args.top_k,
                seed=args.seed,
            )
        )

    combined = combine_rows(rows, args.seed)
    write_jsonl(combined, args.output)
    print(f"Built {len(combined)} blinded delta candidates for rerank windows")
    print(f"Saved annotation pool to {args.output}")


if __name__ == "__main__":
    main()
