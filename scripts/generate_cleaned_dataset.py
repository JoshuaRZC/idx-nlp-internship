import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.text_cleaner import TextCleaner


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a cleaned listing sample from Week 1 remarks."
    )
    parser.add_argument(
        "--input",
        default="data/processed/listing_sample.csv",
        help="Input CSV with a remarks column",
    )
    parser.add_argument(
        "--output",
        default="data/processed/listing_sample_cleaned.csv",
        help="Output CSV with an added remarks_cleaned column",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_csv(input_path)
    cleaner = TextCleaner()
    cleaned = cleaner.clean_dataframe(df, "remarks", "remarks_cleaned")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_path, index=False)

    print(f"Wrote {len(cleaned)} rows to {output_path}")


if __name__ == "__main__":
    main()
