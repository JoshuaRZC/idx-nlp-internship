import argparse
import json
import random
import re
from pathlib import Path

import pandas as pd


RARE_GROUPS = {
    "financing": r"\b(?:seller financ|owner carry|assumable|cash only|all cash|lease option|fha|va financ)\b",
    "investment": r"\b(?:tenant occupied|rental income|investment opportunity|rental opportunity|adu potential|short term rental)\b",
    "hoa": r"\b(?:hoa|homeowners association)\b",
    "lot_size": r"\b(?:acre|acres|sq\.?\s*ft\.?\s*lot|square feet lot)\b",
    "year_built": r"\b(?:built in|year built|yr built)\b",
    "parking": r"\b(?:car garage|carport|rv parking|rv access|underground parking)\b",
    "condition": r"\b(?:fixer|remodel(?:ed|ing)?|renovat(?:ed|ion)|turnkey|turn key)\b",
    "location": r"\b(?:ocean view|mountain view|waterfront|near beach|close to beach|freeway access)\b",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Select a frozen listing-signal evaluation sample.")
    parser.add_argument("--week3-labels", default="data/processed/entity_eval_labels.json")
    parser.add_argument("--week3-source", default="data/processed/listing_sample_cleaned.csv")
    parser.add_argument("--semantic-sample", default="data/processed/listing_semantic_sample_10k.csv")
    parser.add_argument("--output", default="data/processed/listing_signal_eval_source.csv")
    parser.add_argument("--seed", type=int, default=20260730)
    return parser.parse_args()


def label_ids(path):
    labels = json.loads(Path(path).read_text())
    return {int(item["listing_id"]) for item in labels["items"]}


def all_week3_ids():
    paths = (
        "data/processed/entity_train_labels.json",
        "data/processed/entity_dev_labels.json",
        "data/processed/entity_eval_labels.json",
    )
    return set().union(*(label_ids(path) for path in paths if Path(path).exists()))


def week3_records(args, rng):
    labels = json.loads(Path(args.week3_labels).read_text())["items"]
    selected_ids = set(rng.sample(sorted(int(item["listing_id"]) for item in labels), 100))

    source = pd.read_csv(args.week3_source).rename(
        columns={"L_ListingID": "listing_id", "L_Address": "address", "L_City": "city"}
    )
    source["listing_id"] = source["listing_id"].astype(int)
    source = source[source["listing_id"].isin(selected_ids)].copy()
    source["sqft"] = None
    source["sample_group"] = "week3_reviewed"
    source["selection_reason"] = "week3_reviewed_entity_labels"
    return source


def rare_records(args, excluded_ids, rng):
    sample = pd.read_csv(args.semantic_sample)
    sample["listing_id"] = sample["listing_id"].astype(int)
    sample = sample[~sample["listing_id"].isin(excluded_ids)].copy()
    sample["_length"] = sample["remarks_cleaned"].str.len()

    selected = []
    used_ids = set(excluded_ids)
    for group, pattern in RARE_GROUPS.items():
        candidates = sample[
            sample["remarks_cleaned"].str.contains(pattern, flags=re.I, regex=True, na=False)
            & ~sample["listing_id"].isin(used_ids)
        ].sort_values(["_length", "listing_id"])
        pool = candidates.head(100)
        rows = pool.sample(n=10, random_state=rng.randrange(1_000_000)).copy()
        rows["sample_group"] = "rare_10k"
        rows["selection_reason"] = group
        selected.append(rows)
        used_ids.update(rows["listing_id"])

    rare = pd.concat(selected, ignore_index=True)
    remaining = sample[~sample["listing_id"].isin(used_ids)]
    random_rows = remaining.sample(n=20, random_state=rng.randrange(1_000_000)).copy()
    random_rows["sample_group"] = "random_10k"
    random_rows["selection_reason"] = "random_10k"
    return pd.concat([rare, random_rows], ignore_index=True)


def main():
    args = parse_args()
    rng = random.Random(args.seed)
    week3 = week3_records(args, rng)
    extra = rare_records(args, all_week3_ids(), rng)

    columns = [
        "listing_id",
        "address",
        "city",
        "price",
        "beds",
        "baths",
        "sqft",
        "remarks",
        "remarks_cleaned",
        "sample_group",
        "selection_reason",
    ]
    output = pd.concat([week3, extra], ignore_index=True)[columns]
    output = output.sort_values(["sample_group", "selection_reason", "listing_id"])

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    print(f"Wrote {len(output)} listings to {output_path}")
    print(output.groupby(["sample_group", "selection_reason"]).size().to_string())


if __name__ == "__main__":
    main()
