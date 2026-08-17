import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_listing_summaries import load_records


def parse_args():
    parser = argparse.ArgumentParser(description="Select a frozen listing-summary evaluation sample.")
    parser.add_argument("--input-csv", help="Optional listing CSV instead of MySQL")
    parser.add_argument("--signals", default="data/processed/listing_signals.jsonl")
    parser.add_argument("--output", default="data/processed/listing_summary_eval_source.csv")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--database", default="real_estate")
    return parser.parse_args()


def load_signals(path):
    with Path(path).open(encoding="utf-8") as f:
        return {str(row["listing_id"]): row for line in f if (row := json.loads(line))}


def feature_count(signal):
    if not signal:
        return 0
    buckets = ("amenities", "exterior_features", "interior_features", "location_features", "condition", "rooms", "parking")
    return sum(len(signal["text_signals"].get(bucket, [])) for bucket in buckets)


def select_sample(records, signals, seed=42):
    df = pd.DataFrame(records).copy()
    df["listing_id"] = df["listing_id"].astype(str)
    df["feature_count"] = df["listing_id"].map(lambda item: feature_count(signals.get(item)))
    df["remark_length"] = df["remarks"].fillna("").astype(str).str.len()
    complete = df[["city", "price", "beds", "baths"]].notna().all(axis=1)

    groups = [
        (df[complete & (df["feature_count"] >= 2) & (df["remark_length"] >= 160)], 35),
        (df[complete & (df["feature_count"] <= 1) & (df["remark_length"] >= 40)], 10),
        (df[~complete | (df["remark_length"] < 40)], 5),
    ]

    selected = []
    used_ids = set()
    for group, count in groups:
        group = group[~group["listing_id"].isin(used_ids)]
        rows = group.sample(n=min(count, len(group)), random_state=seed + len(selected))
        selected.append(rows)
        used_ids.update(rows["listing_id"])

    sample = pd.concat(selected, ignore_index=True)
    if len(sample) < 50:
        remainder = df[~df["listing_id"].isin(used_ids)]
        sample = pd.concat(
            [sample, remainder.sample(n=50 - len(sample), random_state=seed + 99)],
            ignore_index=True,
        )

    sample = sample.sample(frac=1, random_state=seed).reset_index(drop=True)
    sample["split"] = ["dev"] * 20 + ["test"] * 30
    sample["text_signals"] = sample["listing_id"].map(
        lambda item: json.dumps(signals.get(item, {}).get("text_signals", {}), sort_keys=True)
    )
    return sample.drop(columns=["feature_count", "remark_length"])


def main():
    args = parse_args()
    records = load_records(args)
    sample = select_sample(records, load_signals(args.signals), args.seed)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(output_path, index=False)
    print(f"Wrote {len(sample)} evaluation listings to {output_path}")


if __name__ == "__main__":
    main()
