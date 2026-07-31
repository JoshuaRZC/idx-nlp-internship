import argparse
import csv
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.signal_extractor import SignalExtractor
from scripts.evaluate_listing_signals import signal_pairs


def parse_args():
    parser = argparse.ArgumentParser(description="Create a review table for listing-signal gold labels.")
    parser.add_argument("--labels", default="data/processed/listing_signal_eval_labels.json")
    parser.add_argument("--source", default="data/processed/listing_signal_eval_source.csv")
    parser.add_argument("--taxonomy", default="data/processed/taxonomy.json")
    parser.add_argument("--output", default="data/processed/listing_signal_label_audit.csv")
    return parser.parse_args()


def format_pairs(pairs):
    return "; ".join(
        f"{bucket}: {value}" for bucket, value in sorted(pairs, key=lambda item: (item[0], str(item[1])))
    )


def main():
    args = parse_args()
    labels = json.loads(Path(args.labels).read_text())["items"]
    source = pd.read_csv(args.source).set_index("listing_id")
    extractor = SignalExtractor(taxonomy_path=args.taxonomy)

    rows = []
    for item in labels:
        listing_id = int(item["listing_id"])
        record = source.loc[listing_id].to_dict()
        record["listing_id"] = listing_id
        prediction = extractor.extract_signals(record)

        gold_pairs = signal_pairs(item["text_signal_gold"])
        predicted_pairs = signal_pairs(prediction["text_signals"])
        rows.append(
            {
                "listing_id": listing_id,
                "sample_group": item["sample_group"],
                "selection_reason": item["selection_reason"],
                "gold_signals": format_pairs(gold_pairs),
                "predicted_signals": format_pairs(predicted_pairs),
                "false_positives": format_pairs(predicted_pairs - gold_pairs),
                "false_negatives": format_pairs(gold_pairs - predicted_pairs),
                "remarks": record.get("remarks", ""),
            }
        )

    output = Path(args.output)
    with output.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} review rows to {output}")


if __name__ == "__main__":
    main()
