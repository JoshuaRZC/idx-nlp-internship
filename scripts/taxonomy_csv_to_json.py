import argparse
import json
from pathlib import Path

import pandas as pd


CATEGORIES = [
    "property_type",
    "room",
    "amenity",
    "interior_feature",
    "exterior_feature",
    "location",
    "condition",
    "transaction_or_listing",
]

REQUIRED_COLUMNS = {
    "id",
    "term",
    "category",
    "frequency",
    "ngram_type",
    "source",
    "review_status",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert cleaned taxonomy CSV into taxonomy JSON."
    )
    parser.add_argument(
        "--input",
        default="data/processed/taxonomy_seed_cleaned.csv",
        help="Cleaned taxonomy CSV path",
    )
    parser.add_argument(
        "--output",
        default="data/processed/taxonomy.json",
        help="Output taxonomy JSON path",
    )
    return parser.parse_args()


def parse_aliases(value):
    if pd.isna(value) or not str(value).strip():
        return []
    return [alias.strip() for alias in str(value).split(";") if alias.strip()]


def validate_columns(df):
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")


def build_taxonomy(input_path):
    df = pd.read_csv(input_path)
    validate_columns(df)

    df = df.sort_values(["category", "id"]).reset_index(drop=True)
    category_counts = df["category"].value_counts().reindex(CATEGORIES, fill_value=0)

    terms = []
    for row in df.to_dict(orient="records"):
        term = {
            "id": row["id"],
            "term": row["term"],
            "category": row["category"],
            "aliases": parse_aliases(row.get("aliases")),
            "frequency": int(row["frequency"]),
            "ngram_type": row["ngram_type"],
            "source": row["source"],
            "review_status": row["review_status"],
        }
        terms.append(term)

    return {
        "version": "0.1",
        "name": "Real Estate Listing Taxonomy",
        "description": "Week 1 taxonomy seed for real estate listing remarks and search queries.",
        "generated_from": str(input_path),
        "categories": CATEGORIES,
        "category_counts": category_counts.to_dict(),
        "terms": terms,
    }


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    taxonomy = build_taxonomy(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(taxonomy, indent=2) + "\n")

    print(f"Converted {len(taxonomy['terms'])} terms to {output_path}")


if __name__ == "__main__":
    main()
