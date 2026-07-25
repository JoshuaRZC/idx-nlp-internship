import argparse
from pathlib import Path

import mysql.connector
import pandas as pd

from text_cleaning import TextCleaner


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
WHERE L_Remarks IS NOT NULL
  AND TRIM(L_Remarks) <> ''
ORDER BY CRC32(CONCAT(CAST(L_ListingID AS CHAR), 'week5-semantic-sample'))
LIMIT %(limit)s
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a fixed sample for Week 5 search.")
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--output", default="data/processed/listing_semantic_sample_10k.csv")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--database", default="real_estate")
    return parser.parse_args()


def clean_sample(df: pd.DataFrame):
    cleaner = TextCleaner()
    return cleaner.clean_dataframe(df, "remarks", "remarks_cleaned")


def main():
    args = parse_args()
    conn = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )

    df = pd.read_sql(QUERY, conn, params={"limit": args.limit})
    conn.close()

    df = clean_sample(df)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"Wrote {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
