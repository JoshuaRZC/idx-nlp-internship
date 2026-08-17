import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_listing_summaries import load_jsonl


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare a local self-review sheet for listing summaries.")
    parser.add_argument("--source", default="data/processed/listing_summary_eval_source.csv")
    parser.add_argument("--summaries", default="data/processed/listing_summaries.jsonl")
    parser.add_argument("--output", default="data/processed/listing_summary_self_review.csv")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def build_review_rows(source, summaries, seed=42):
    rows = source[source["split"] == "test"].sample(n=20, random_state=seed).copy()
    rows["listing_id"] = rows["listing_id"].astype(str)
    rows["summary"] = rows["listing_id"].map(summaries)
    rows["factual_accuracy"] = ""
    rows["usefulness"] = ""
    rows["concision"] = ""
    rows["notes"] = ""
    columns = [
        "listing_id",
        "summary",
        "city",
        "price",
        "beds",
        "baths",
        "remarks",
        "factual_accuracy",
        "usefulness",
        "concision",
        "notes",
    ]
    return rows[columns]


def main():
    args = parse_args()
    source = pd.read_csv(args.source)
    review = build_review_rows(source, load_jsonl(args.summaries), args.seed)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(output_path, index=False)
    print(f"Wrote {len(review)} self-review rows to {output_path}")


if __name__ == "__main__":
    main()
