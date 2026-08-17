import argparse
import json
import sys
from pathlib import Path

import mysql.connector
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.listing_summarizer import ListingSummarizer


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
    parser = argparse.ArgumentParser(description="Generate compact listing summaries.")
    parser.add_argument("--input-csv", help="Optional listing CSV instead of MySQL")
    parser.add_argument("--signals", default="data/processed/listing_signals.jsonl")
    parser.add_argument("--output", default="data/processed/listing_summaries.jsonl")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--database", default="real_estate")
    return parser.parse_args()


def load_records(args):
    if args.input_csv:
        records = pd.read_csv(args.input_csv).to_dict("records")
    else:
        conn = mysql.connector.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
        )
        records = pd.read_sql(QUERY, conn).to_dict("records")
        conn.close()
    return records[: args.limit] if args.limit else records


def load_signals(path):
    with Path(path).open(encoding="utf-8") as f:
        return {str(row["listing_id"]): row for line in f if (row := json.loads(line))}


def build_summaries(records, signals, summarizer=None):
    summarizer = summarizer or ListingSummarizer()
    output = []
    for record in records:
        listing_id = str(record["listing_id"])
        output.append(
            {
                "listing_id": listing_id,
                "summary": summarizer.summarize(record, signals.get(listing_id)),
            }
        )
    return output


def write_jsonl(records, path):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    args = parse_args()
    records = load_records(args)
    summaries = build_summaries(records, load_signals(args.signals))
    write_jsonl(summaries, args.output)
    print(f"Wrote {len(summaries)} listing summaries to {args.output}")


if __name__ == "__main__":
    main()
