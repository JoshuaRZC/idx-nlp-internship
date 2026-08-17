import argparse
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.compliance_checker import ComplianceChecker  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Run Fair Housing checks on listing remarks.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output", default="data/processed/listing_compliance_results.jsonl")
    parser.add_argument("--id-column", default="listing_id")
    parser.add_argument("--text-column", default="remarks")
    return parser.parse_args()


def check_records(records, id_column="listing_id", text_column="remarks", checker=None):
    checker = checker or ComplianceChecker()
    output = []
    for record in records:
        result = checker.check_listing(record.get(text_column))
        output.append({"listing_id": str(record[id_column]), **result})
    return output


def write_jsonl(records, path):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    args = parse_args()
    records = pd.read_csv(args.input_csv).to_dict("records")
    results = check_records(records, args.id_column, args.text_column)
    write_jsonl(results, args.output)
    print(f"Wrote {len(results)} compliance results to {args.output}")


if __name__ == "__main__":
    main()
