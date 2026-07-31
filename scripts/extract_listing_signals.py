import argparse
import json
import sys
from pathlib import Path

import mysql.connector
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.signal_extractor import SignalExtractor


QUERY = """
SELECT
    L_ListingID AS listing_id,
    L_Address AS address,
    L_City AS city,
    L_SystemPrice AS price,
    L_Keyword2 AS beds,
    LM_Dec_3 AS baths,
    LM_Int2_3 AS sqft,
    L_Remarks AS remarks
FROM rets_property
ORDER BY L_ListingID
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Extract listing-level NLP signals.")
    parser.add_argument("--input-csv", help="Optional CSV input instead of MySQL")
    parser.add_argument("--output", help="Output JSONL path")
    parser.add_argument("--taxonomy", default="data/processed/taxonomy.json")
    parser.add_argument("--limit", type=int, help="Optional row limit for local checks")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--database", default="real_estate")
    return parser.parse_args()


def load_records(args):
    if args.input_csv:
        df = pd.read_csv(args.input_csv)
        if args.limit:
            df = df.head(args.limit)
        return df.to_dict("records")

    query = QUERY
    params = None
    if args.limit:
        query += "\nLIMIT %(limit)s"
        params = {"limit": args.limit}

    conn = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df.to_dict("records")


def write_jsonl(records, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    args = parse_args()
    records = load_records(args)

    extractor = SignalExtractor(taxonomy_path=args.taxonomy)
    signals = extractor.extract_many(records)

    default_output = (
        "data/processed/listing_signals_10k.jsonl"
        if args.input_csv
        else "data/processed/listing_signals.jsonl"
    )
    output_path = Path(args.output or default_output)
    write_jsonl(signals, output_path)
    print(f"Wrote {len(signals)} listing signal records to {output_path}")


if __name__ == "__main__":
    main()
