import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description="Create a listing-summary reference-label scaffold.")
    parser.add_argument("--source", default="data/processed/listing_summary_eval_source.csv")
    parser.add_argument("--output", default="data/processed/listing_summary_eval_labels.json")
    return parser.parse_args()


def value_or_none(value):
    return None if pd.isna(value) else value


def build_items(df):
    items = []
    for index, row in df.iterrows():
        items.append(
            {
                "id": f"listing_summary_{index + 1:04d}",
                "listing_id": str(row["listing_id"]),
                "split": row["split"],
                "reference_summary": "",
                "facts": {
                    "price": value_or_none(row["price"]),
                    "beds": value_or_none(row["beds"]),
                    "baths": value_or_none(row["baths"]),
                    "city": value_or_none(row["city"]),
                },
                "feature_gold": [],
            }
        )
    return items


def main():
    args = parse_args()
    items = build_items(pd.read_csv(args.source))
    payload = {
        "items": items,
        "notes": {
            "reference_summary": "Write independently from MLS fields and remarks before reviewing generated summaries.",
            "feature_gold": "List up to two explicit, summary-worthy features from the original remark.",
        },
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} label scaffolds to {output_path}")


if __name__ == "__main__":
    main()
