import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.signal_schema import SIGNAL_BUCKETS, empty_text_signals, normalize_text_signals


ENTITY_BUCKETS = {
    "amenity": "amenities",
    "condition": "condition",
    "interior_feature": "interior_features",
    "exterior_feature": "exterior_features",
    "location": "location_features",
    "room": "rooms",
    "property_type": "property_type",
    "parking": "parking",
}

NUMERIC_LABELS = {
    "price": "price",
    "bedrooms": "beds",
    "bathrooms": "baths",
    "sqft": "sqft",
    "lot_size": "lot_size",
    "year_built": "year_built",
    "hoa_fee": "hoa_fee",
    "stories": "stories",
}

FINANCING_TERMS = (
    "financing",
    "loan",
    "cash only",
    "all cash",
    "owner carry",
    "assumable",
    "lease option",
    "option to purchase",
)
INVESTMENT_TERMS = {"investment", "rental", "tenant occupied"}


def parse_args():
    parser = argparse.ArgumentParser(description="Build Week 6 listing-signal gold labels.")
    parser.add_argument("--source", default="data/processed/listing_signal_eval_source.csv")
    parser.add_argument("--week3-labels", default="data/processed/entity_eval_labels.json")
    parser.add_argument("--annotations", default="data/processed/listing_signal_eval_annotations.json")
    parser.add_argument("--output", default="data/processed/listing_signal_eval_labels.json")
    return parser.parse_args()


def normalize_text(value):
    text = str(value).lower()
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^\w\s.+]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def add_signal(signals, bucket, value):
    if value not in signals[bucket]:
        signals[bucket].append(value)


def transaction_bucket(value):
    normalized = normalize_text(value)
    if any(term in normalized for term in FINANCING_TERMS):
        return "financing_terms"
    if normalized in INVESTMENT_TERMS:
        return "investment_features"
    return "transaction_features"


def week3_gold(item):
    text_signals = empty_text_signals()
    remark_numeric = {name: None for name in NUMERIC_LABELS.values()}

    for entity in item["entities"]:
        label = entity["label"]
        value = entity["value"]
        if label in ENTITY_BUCKETS:
            add_signal(text_signals, ENTITY_BUCKETS[label], value)
        elif label == "transaction_or_listing":
            add_signal(text_signals, transaction_bucket(value), value)
        elif label in NUMERIC_LABELS:
            remark_numeric[NUMERIC_LABELS[label]] = value

    return text_signals, remark_numeric


def manual_gold(annotations, listing_id):
    annotation = annotations[str(listing_id)]
    text_signals = empty_text_signals()
    for bucket, values in annotation.get("text_signals", {}).items():
        for value in values:
            add_signal(text_signals, bucket, value)

    remark_numeric = {name: None for name in NUMERIC_LABELS.values()}
    remark_numeric.update(annotation.get("remark_numeric", {}))
    return text_signals, remark_numeric


def apply_audited_corrections(signals, listing_id):
    corrections = {
        1149834826: {"remove": {"financing_terms": ["fha loan", "va loan"]}},
    }.get(listing_id, {})

    for bucket, values in corrections.get("remove", {}).items():
        signals[bucket] = [value for value in signals[bucket] if value not in values]
    for bucket, values in corrections.get("add", {}).items():
        for value in values:
            add_signal(signals, bucket, value)
    return signals


def structured_gold(row):
    values = {}
    for field in ("price", "beds", "baths", "sqft"):
        value = row[field]
        if pd.notna(value):
            values[field] = int(value) if float(value).is_integer() else float(value)
        else:
            values[field] = None
    return values


def main():
    args = parse_args()
    source = pd.read_csv(args.source)
    annotations = json.loads(Path(args.annotations).read_text())
    week3_items = {
        int(item["listing_id"]): item
        for item in json.loads(Path(args.week3_labels).read_text())["items"]
    }

    items = []
    for row in source.itertuples(index=False):
        listing_id = int(row.listing_id)
        if row.sample_group == "week3_reviewed":
            text_signals, remark_numeric = week3_gold(week3_items[listing_id])
        else:
            text_signals, remark_numeric = manual_gold(annotations, listing_id)

        text_signals = apply_audited_corrections(text_signals, listing_id)
        text_signals = normalize_text_signals(text_signals)

        items.append(
            {
                "id": f"listing_signal_eval_{len(items) + 1:04d}",
                "listing_id": listing_id,
                "sample_group": row.sample_group,
                "selection_reason": row.selection_reason,
                "structured_numeric_gold": structured_gold(row._asdict()),
                "remark_numeric_gold": remark_numeric,
                "text_signal_gold": text_signals,
            }
        )

    output = {
        "items": items,
        "text_signal_buckets": list(SIGNAL_BUCKETS),
        "annotation_rules": {
            "structured_priority": "MLS fields override remark-derived values.",
            "text_scope": "Only explicit, search-relevant signals stated in the listing remark.",
            "normalization": "Gold values use the shared production signal vocabulary; generic and duplicate concepts are excluded.",
        },
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n")
    print(f"Wrote {len(items)} labeled listings to {args.output}")


if __name__ == "__main__":
    main()
