import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.query_intent_classifier import QueryIntentClassifier  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Train the Week 7 query intent classifier.")
    parser.add_argument("--labels", default="data/processed/query_intent_labels.json")
    parser.add_argument("--model-dir", default="data/models/query_intent")
    parser.add_argument("--c", type=float, default=1.0)
    parser.add_argument("--browsing-weight", type=float, default=1.0)
    parser.add_argument("--min-df", type=int, default=1)
    parser.add_argument("--sublinear-tf", action="store_true")
    return parser.parse_args()


def load_items(path):
    payload = json.loads(Path(path).read_text())
    return payload["items"]


def main():
    args = parse_args()
    items = load_items(args.labels)
    train_items = [item for item in items if item["split"] == "train"]

    class_weight = None
    if args.browsing_weight != 1.0:
        class_weight = {"browsing": args.browsing_weight}

    classifier = QueryIntentClassifier(
        c=args.c,
        class_weight=class_weight,
        min_df=args.min_df,
        sublinear_tf=args.sublinear_tf,
    ).fit(
        [item["query"] for item in train_items],
        [item["label"] for item in train_items],
    )
    classifier.save(args.model_dir)
    print(f"Trained on {len(train_items)} queries")
    print(f"Configuration: C={args.c}, browsing_weight={args.browsing_weight}, min_df={args.min_df}")
    print(f"Saved model to {Path(args.model_dir)}")


if __name__ == "__main__":
    main()
