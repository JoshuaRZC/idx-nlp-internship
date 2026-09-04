"""Build a blinded candidate pool for manual search-relevance annotation."""

import argparse
import json
import random
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.search_service import SearchService  # noqa: E402


POOL_VARIANTS = (
    "bm25_only",
    "dense_only",
    "dense_signal",
    "dense_bm25_signal_rrf",
    "hybrid_cross_encoder",
)

DISPLAY_FIELDS = ("listing_id", "city", "price", "beds", "baths", "sqft", "remarks_cleaned")


def parse_args():
    parser = argparse.ArgumentParser(description="Build a blinded search-relevance annotation pool.")
    parser.add_argument("--queries", default="data/processed/search_relevance_queries.json")
    parser.add_argument("--output", default="data/processed/search_relevance_annotation_pool.jsonl")
    parser.add_argument("--search-root", default="data/models/search")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start", type=int, default=0, help="Zero-based inclusive query position.")
    parser.add_argument("--end", type=int, help="Zero-based exclusive query position.")
    parser.add_argument("--append", action="store_true", help="Append rows to an existing output file.")
    return parser.parse_args()


def load_query_dataset(path):
    payload = json.loads(Path(path).read_text())
    if not payload.get("snapshot_id"):
        raise ValueError("Query dataset must include snapshot_id.")
    if not isinstance(payload.get("items"), list):
        raise ValueError("Query dataset must include an items list.")
    return payload


def build_pool(service, query_dataset, top_k=5, seed=42, variants=POOL_VARIANTS):
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    if service.snapshot.snapshot_id != query_dataset["snapshot_id"]:
        raise ValueError("Active snapshot does not match the query dataset.")

    items = []
    seen_query_ids = set()
    for position, query_item in enumerate(query_dataset["items"], start=1):
        query_id = query_item["id"]
        if query_id in seen_query_ids:
            raise ValueError(f"Duplicate query ID: {query_id}")
        seen_query_ids.add(query_id)
        print(f"Pooling {position}/{len(query_dataset['items'])}: {query_id}", flush=True)

        candidates = {}
        for variant in variants:
            response = service.search_experiment(query_item["query"], variant, top_k=top_k)
            if not response["ok"]:
                raise ValueError(f"Query {query_id} is not answerable: {response['message']}")
            if response["meta"].get("effective_sort") != "relevance":
                raise ValueError(f"Query {query_id} is not a relevance query.")
            if len(response["results"]) != top_k:
                raise ValueError(f"Query {query_id} returned fewer than {top_k} results for {variant}.")

            for result in response["results"]:
                candidates.setdefault(str(result["listing_id"]), result)

        rows = []
        for listing_id, result in candidates.items():
            row = {
                "query_id": query_id,
                "query": query_item["query"],
                "split": query_item["split"],
                "snapshot_id": query_dataset["snapshot_id"],
                "annotation_status": "pending",
                "relevance_grade": None,
                "rationale": "",
            }
            row.update({field: result.get(field) for field in DISPLAY_FIELDS})
            rows.append(row)

        random.Random(f"{seed}:{query_id}").shuffle(rows)
        for annotation_order, row in enumerate(rows, start=1):
            row["annotation_order"] = annotation_order
        items.extend(rows)

    return items


def write_jsonl(items, path, append=False):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with output.open(mode, encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def main():
    args = parse_args()
    query_dataset = load_query_dataset(args.queries)
    selected = query_dataset["items"][args.start:args.end]
    if not selected:
        raise ValueError("The requested query range is empty.")
    query_dataset = {**query_dataset, "items": selected}
    service = SearchService.from_active_snapshot(
        search_root=args.search_root,
        enable_cross_encoder=True,
    )
    service.warm_up(include_cross_encoder=True)
    items = build_pool(service, query_dataset, args.top_k, args.seed)
    write_jsonl(items, args.output, append=args.append)
    print(f"Built {len(items)} blinded candidates for {len(query_dataset['items'])} queries")
    print(f"Snapshot: {query_dataset['snapshot_id']}")
    print(f"Saved annotation pool to {args.output}")


if __name__ == "__main__":
    main()
