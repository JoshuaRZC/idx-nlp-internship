"""Convert a complete blind-review grade map into compact relevance qrels."""

import argparse
import json
from pathlib import Path


VALID_GRADES = {0, 1, 2, 3}


def parse_args():
    parser = argparse.ArgumentParser(description="Finalize manually reviewed search relevance labels.")
    parser.add_argument("--pool", default="data/processed/search_relevance_annotation_pool.jsonl")
    parser.add_argument("--grades", default="data/processed/search_relevance_manual_grades.json")
    parser.add_argument("--output", default="data/processed/search_relevance_qrels.jsonl")
    return parser.parse_args()


def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_grade_map(path):
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload.get("grades"), dict):
        raise ValueError("Grade map must contain a grades object.")
    return payload


def finalize(pool, grade_map):
    snapshots = {item["snapshot_id"] for item in pool}
    if len(snapshots) != 1:
        raise ValueError("Annotation pool must use exactly one snapshot.")
    snapshot_id = snapshots.pop()
    if grade_map.get("snapshot_id") != snapshot_id:
        raise ValueError("Grade map does not match the annotation pool snapshot.")

    expected = {(item["query_id"], str(item["listing_id"])) for item in pool}
    supplied = {
        (query_id, str(listing_id))
        for query_id, values in grade_map["grades"].items()
        for listing_id in values
    }
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(f"Grade map mismatch. Missing: {missing[:5]}; extra: {extra[:5]}")

    labels = []
    for item in pool:
        grade = grade_map["grades"][item["query_id"]][str(item["listing_id"])]
        if grade not in VALID_GRADES:
            raise ValueError(f"Invalid grade for {item['query_id']} / {item['listing_id']}")
        labels.append(
            {
                "query_id": item["query_id"],
                "listing_id": str(item["listing_id"]),
                "snapshot_id": snapshot_id,
                "annotation_status": "complete",
                "relevance_grade": grade,
            }
        )
    return labels


def write_jsonl(items, path):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item) + "\n")


def main():
    args = parse_args()
    labels = finalize(load_jsonl(args.pool), load_grade_map(args.grades))
    write_jsonl(labels, args.output)
    print(f"Finalized {len(labels)} relevance labels")


if __name__ == "__main__":
    main()
