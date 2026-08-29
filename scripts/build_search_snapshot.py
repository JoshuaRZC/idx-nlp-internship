"""Build and activate a pass-only search snapshot from MySQL."""

import argparse
import sys
from pathlib import Path

import mysql.connector

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.search_snapshot import SearchSnapshotBuilder


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
    parser = argparse.ArgumentParser(description="Build a versioned pass-only public search snapshot.")
    parser.add_argument("--snapshot-root", default="data/models/search_snapshots")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--taxonomy", default="data/processed/taxonomy.json")
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--no-activate", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--database", default="real_estate")
    return parser.parse_args()


def load_records(args):
    connection = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        connection.start_transaction(consistent_snapshot=True)
        cursor.execute(QUERY)
        records = cursor.fetchall()
        connection.commit()
        return records
    finally:
        cursor.close()
        connection.close()


def main():
    args = parse_args()
    records = load_records(args)
    builder = SearchSnapshotBuilder(taxonomy_path=args.taxonomy, model_name=args.model)
    path = builder.build(
        records,
        snapshot_root=args.snapshot_root,
        snapshot_id=args.snapshot_id,
        activate=not args.no_activate,
    )
    print(f"Built search snapshot: {path}")


if __name__ == "__main__":
    main()
