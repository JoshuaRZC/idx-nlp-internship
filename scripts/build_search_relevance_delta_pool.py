"""Build a blinded pool for newly surfaced, unjudged search results."""

import argparse
import random
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_search_relevance_pool import DISPLAY_FIELDS, write_jsonl  # noqa: E402
from scripts.evaluate_search_relevance import (  # noqa: E402
    load_manifest,
    load_qrels,
    load_query_dataset,
    validate_labels,
    validate_manifest,
)
from src.real_estate_nlp.search_service import SearchService  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Build a blinded delta pool for unjudged retrieval results.")
    parser.add_argument("--queries", default="data/processed/search_relevance_queries.json")
    parser.add_argument("--qrels", default="data/processed/search_relevance_qrels.jsonl")
    parser.add_argument("--manifest", default="data/processed/search_relevance_manifest.json")
    parser.add_argument("--output", default="data/processed/search_relevance_cross_encoder_delta_pool.jsonl")
    parser.add_argument("--search-root", default="data/models/search")
    parser.add_argument("--variant", default="hybrid_cross_encoder")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def build_delta_pool(service, query_dataset, qrels, variant, split="dev", top_k=5, seed=42):
    labels = validate_labels(query_dataset, qrels, service.snapshot.snapshot_id)
    rows = []
    for query_item in query_dataset["items"]:
        if query_item["split"] != split:
            continue
        response = service.search_experiment(query_item["query"], variant, top_k=top_k)
        if not response["ok"] or response["meta"].get("effective_sort") != "relevance":
            raise ValueError(f"Query {query_item['id']} cannot be pooled for relevance annotation.")
        if len(response["results"]) != top_k:
            raise ValueError(f"Query {query_item['id']} returned fewer than {top_k} results.")

        query_rows = []
        for result in response["results"]:
            listing_id = str(result["listing_id"])
            if (query_item["id"], listing_id) in labels:
                continue
            row = {
                "query_id": query_item["id"],
                "query": query_item["query"],
                "split": split,
                "snapshot_id": service.snapshot.snapshot_id,
                "annotation_status": "pending",
                "relevance_grade": None,
                "rationale": "",
            }
            row.update({field: result.get(field) for field in DISPLAY_FIELDS})
            query_rows.append(row)

        random.Random(f"{seed}:{query_item['id']}").shuffle(query_rows)
        for annotation_order, row in enumerate(query_rows, start=1):
            row["annotation_order"] = annotation_order
        rows.extend(query_rows)
    return rows


def main():
    args = parse_args()
    query_dataset = load_query_dataset(args.queries)
    qrels = load_qrels(args.qrels)
    service = SearchService.from_active_snapshot(search_root=args.search_root, enable_cross_encoder=True)
    service.warm_up(include_cross_encoder=True)
    validate_manifest(load_manifest(args.manifest), args.queries, args.qrels, service.snapshot.snapshot_id)
    rows = build_delta_pool(service, query_dataset, qrels, args.variant, args.split, args.top_k, args.seed)
    write_jsonl(rows, args.output)
    print(f"Built {len(rows)} blinded delta candidates for {args.split}")
    print(f"Saved annotation pool to {args.output}")


if __name__ == "__main__":
    main()
