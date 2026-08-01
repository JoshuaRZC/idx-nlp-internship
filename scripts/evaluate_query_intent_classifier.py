import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.query_intent_classifier import QueryIntentClassifier  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate the Week 7 query intent classifier.")
    parser.add_argument("--labels", default="data/processed/query_intent_labels.json")
    parser.add_argument("--model-dir", default="data/models/query_intent")
    parser.add_argument("--output", default="data/processed/query_intent_eval_results.json")
    parser.add_argument("--split", choices=["dev", "test"], default="test")
    parser.add_argument("--error-limit", type=int, default=20)
    return parser.parse_args()


def load_items(path):
    return json.loads(Path(path).read_text())["items"]


def evaluate_items(items, classifier, error_limit=20):
    queries = [item["query"] for item in items]
    expected = [item["label"] for item in items]
    predictions = classifier.predict_many(queries)
    predicted = [item["label"] for item in predictions]
    labels = list(QueryIntentClassifier.LABELS)

    precision, recall, f1, support = precision_recall_fscore_support(
        expected,
        predicted,
        labels=labels,
        zero_division=0,
    )
    per_label = {
        label: {
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(labels)
    }

    errors = []
    confidence_by_result = defaultdict(list)
    for item, prediction in zip(items, predictions):
        correct = item["label"] == prediction["label"]
        confidence_by_result["correct" if correct else "incorrect"].append(prediction["confidence"])
        if not correct and len(errors) < error_limit:
            errors.append(
                {
                    "id": item["id"],
                    "query": item["query"],
                    "expected": item["label"],
                    "predicted": prediction["label"],
                    "confidence": prediction["confidence"],
                }
            )

    confidences = [item["confidence"] for item in predictions]
    return {
        "queries_evaluated": len(items),
        "accuracy": float(accuracy_score(expected, predicted)),
        "per_label": per_label,
        "confusion_matrix": {
            "labels": labels,
            "values": confusion_matrix(expected, predicted, labels=labels).tolist(),
        },
        "confidence": {
            "mean": sum(confidences) / len(confidences),
            "mean_correct": mean(confidence_by_result["correct"]),
            "mean_incorrect": mean(confidence_by_result["incorrect"]),
            "uncertain_count": sum(item["is_uncertain"] for item in predictions),
            "bins": confidence_bins(expected, predicted, confidences),
        },
        "errors": errors,
    }


def mean(values):
    return sum(values) / len(values) if values else None


def confidence_bins(expected, predicted, confidences):
    bounds = ((0.0, 0.60), (0.60, 0.75), (0.75, 0.90), (0.90, 1.01))
    bins = []
    for lower, upper in bounds:
        positions = [
            index
            for index, confidence in enumerate(confidences)
            if lower <= confidence < upper
        ]
        correct = sum(expected[index] == predicted[index] for index in positions)
        bins.append(
            {
                "range": f"{lower:.2f}-{min(upper, 1.0):.2f}",
                "count": len(positions),
                "accuracy": correct / len(positions) if positions else None,
            }
        )
    return bins


def main():
    args = parse_args()
    items = [item for item in load_items(args.labels) if item["split"] == args.split]
    classifier = QueryIntentClassifier.load(args.model_dir)
    results = evaluate_items(items, classifier, args.error_limit)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2))
    print(f"Evaluated {results['queries_evaluated']} {args.split} queries")
    print(f"Accuracy: {results['accuracy']:.3f}")
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
