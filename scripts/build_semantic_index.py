import argparse
import sys
from pathlib import Path

import mysql.connector
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.semantic_search import DEFAULT_MODEL_NAME, SemanticSearcher
from src.real_estate_nlp.text_cleaner import TextCleaner


FULL_QUERY = """
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
ORDER BY L_ListingID
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Build a FAISS index for listing remarks.")
    parser.add_argument("--source", choices=["sample_10k", "full"], default="sample_10k")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Load the embedding model from the local Hugging Face cache only.",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--sample-path", default="data/processed/listing_semantic_sample_10k.csv")
    parser.add_argument("--output-dir", default="data/models/semantic")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--database", default="real_estate")
    return parser.parse_args()


def load_sample(path: str):
    return pd.read_csv(path)


def load_full(args):
    conn = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )
    df = pd.read_sql(FULL_QUERY, conn)
    conn.close()

    cleaner = TextCleaner()
    return cleaner.clean_dataframe(df, "remarks", "remarks_cleaned")


def main():
    args = parse_args()
    if args.source == "sample_10k":
        df = load_sample(args.sample_path)
    else:
        df = load_full(args)

    records = df.to_dict("records")
    searcher = SemanticSearcher(
        model_name=args.model_name,
        local_files_only=args.local_files_only,
        batch_size=args.batch_size,
    ).build_index(records)
    output_dir = searcher.artifact_dir(args.output_dir)
    searcher.save(output_dir, args.source)

    print(f"Built {args.source} index with {len(searcher.metadata)} listings")
    print(f"Saved artifacts to {Path(output_dir)}")


if __name__ == "__main__":
    main()
