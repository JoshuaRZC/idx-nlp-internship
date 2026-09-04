"""Record the exact query and qrels files used for search relevance evaluation."""

import argparse
import hashlib
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Freeze search relevance evaluation assets.")
    parser.add_argument("--queries", default="data/processed/search_relevance_queries.json")
    parser.add_argument("--qrels", default="data/processed/search_relevance_qrels.jsonl")
    parser.add_argument("--output", default="data/processed/search_relevance_manifest.json")
    return parser.parse_args()


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_manifest(queries_path, qrels_path):
    queries = json.loads(Path(queries_path).read_text())
    snapshot_id = queries.get("snapshot_id")
    if not snapshot_id:
        raise ValueError("Query dataset must include snapshot_id.")
    return {
        "snapshot_id": snapshot_id,
        "queries_sha256": file_sha256(queries_path),
        "qrels_sha256": file_sha256(qrels_path),
        "query_count": len(queries.get("items", [])),
        "split_counts": {
            split: sum(item.get("split") == split for item in queries.get("items", []))
            for split in ("dev", "test")
        },
    }


def main():
    args = parse_args()
    manifest = build_manifest(args.queries, args.qrels)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen {manifest['query_count']} queries for snapshot {manifest['snapshot_id']}")


if __name__ == "__main__":
    main()
