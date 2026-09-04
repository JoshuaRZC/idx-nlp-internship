"""Merge fully reviewed blind delta labels into an existing qrels file."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.finalize_search_relevance_labels import VALID_GRADES, load_jsonl, write_jsonl


def parse_args():
    parser = argparse.ArgumentParser(description="Merge reviewed search relevance delta labels.")
    parser.add_argument("--qrels", default="data/processed/search_relevance_qrels.jsonl")
    parser.add_argument("--delta-pool", default="data/processed/search_relevance_cross_encoder_delta_pool.jsonl")
    parser.add_argument("--delta-grades", default="data/processed/search_relevance_cross_encoder_delta_manual_grades.json")
    parser.add_argument("--output", default="data/processed/search_relevance_qrels_expanded.jsonl")
    return parser.parse_args()


def load_grade_map(path):
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload.get("grades"), dict):
        raise ValueError("Delta grade file must contain a grades object.")
    return payload


def merge_qrels(qrels, delta_pool, grade_map):
    snapshots = {item["snapshot_id"] for item in qrels + delta_pool}
    if len(snapshots) != 1:
        raise ValueError("Base qrels and delta pool must use the same snapshot.")
    snapshot_id = snapshots.pop()
    if grade_map.get("snapshot_id") != snapshot_id:
        raise ValueError("Delta grades do not match the qrels snapshot.")

    base_keys = {(item["query_id"], str(item["listing_id"])) for item in qrels}
    delta_keys = {(item["query_id"], str(item["listing_id"])) for item in delta_pool}
    if base_keys & delta_keys:
        raise ValueError("Delta pool contains candidates already present in qrels.")

    supplied = {
        (query_id, str(listing_id))
        for query_id, values in grade_map["grades"].items()
        for listing_id in values
    }
    if supplied != delta_keys:
        raise ValueError("Delta grade map does not exactly match the delta pool.")

    additions = []
    for item in delta_pool:
        grade = grade_map["grades"][item["query_id"]][str(item["listing_id"])]
        if grade not in VALID_GRADES:
            raise ValueError(f"Invalid grade for {item['query_id']} / {item['listing_id']}")
        additions.append(
            {
                "query_id": item["query_id"],
                "listing_id": str(item["listing_id"]),
                "snapshot_id": snapshot_id,
                "annotation_status": "complete",
                "relevance_grade": grade,
            }
        )
    return qrels + additions


def main():
    args = parse_args()
    merged = merge_qrels(load_jsonl(args.qrels), load_jsonl(args.delta_pool), load_grade_map(args.delta_grades))
    write_jsonl(merged, args.output)
    print(f"Merged {len(merged)} qrels")


if __name__ == "__main__":
    main()
