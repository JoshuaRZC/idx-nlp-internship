import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.signal_extractor import SignalExtractor


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate listing-level signal extraction.")
    parser.add_argument("--labels", default="data/processed/listing_signal_eval_labels.json")
    parser.add_argument("--source", default="data/processed/listing_signal_eval_source.csv")
    parser.add_argument("--taxonomy", default="data/processed/taxonomy.json")
    parser.add_argument("--output", default="data/processed/listing_signal_eval_results.json")
    parser.add_argument("--error-limit", type=int, default=20)
    return parser.parse_args()


def load_labels(path):
    return json.loads(Path(path).read_text())["items"]


def load_records(path, labels):
    source = pd.read_csv(path)
    listing_ids = {int(item["listing_id"]) for item in labels}
    records = source[source["listing_id"].isin(listing_ids)].to_dict("records")
    if len(records) != len(labels):
        raise ValueError("Source data does not contain every labeled listing.")
    return records


NUMERIC_FIELDS = (
    "price",
    "beds",
    "baths",
    "sqft",
    "lot_size",
    "year_built",
    "hoa_fee",
    "stories",
)


def evaluate_records(predictions, labels, error_limit=20):
    predicted_by_id = {int(item["listing_id"]): item for item in predictions}
    labels_by_id = {int(item["listing_id"]): item for item in labels}
    if predicted_by_id.keys() != labels_by_id.keys():
        raise ValueError("Predictions and labels must contain the same listing IDs.")

    structured = _numeric_metrics(predicted_by_id, labels_by_id, "structured_numeric_gold")
    fallback = _fallback_metrics(predicted_by_id, labels_by_id)
    free_text = _text_metrics(predicted_by_id, labels_by_id, error_limit)
    keyword_integrity = _keyword_integrity(predicted_by_id)

    return {
        "listings_evaluated": len(labels),
        "structured_fields": structured,
        "remark_numeric_fallback": fallback,
        "free_text": free_text,
        "keyword_integrity": keyword_integrity,
    }


def _numeric_metrics(predicted_by_id, labels_by_id, gold_field):
    per_field = {field: {"correct": 0, "support": 0} for field in NUMERIC_FIELDS}
    exact_records = 0
    eligible_records = 0
    errors = []

    for listing_id, gold in labels_by_id.items():
        expected = gold[gold_field]
        predicted = predicted_by_id[listing_id]["numeric_signals"]
        eligible = {field: value for field, value in expected.items() if value is not None}
        if not eligible:
            continue

        eligible_records += 1
        record_is_exact = True
        for field, value in eligible.items():
            per_field[field]["support"] += 1
            if values_match(predicted.get(field), value):
                per_field[field]["correct"] += 1
            else:
                record_is_exact = False
                errors.append(
                    {
                        "listing_id": listing_id,
                        "field": field,
                        "expected": value,
                        "predicted": predicted.get(field),
                    }
                )
        exact_records += record_is_exact

    return {
        "accuracy": ratio(
            sum(item["correct"] for item in per_field.values()),
            sum(item["support"] for item in per_field.values()),
        ),
        "exact_record_accuracy": ratio(exact_records, eligible_records),
        "eligible_records": eligible_records,
        "per_field": {
            field: {**item, "accuracy": ratio(item["correct"], item["support"])}
            for field, item in per_field.items()
            if item["support"]
        },
        "errors": errors,
    }


def _fallback_metrics(predicted_by_id, labels_by_id):
    adjusted_labels = {}
    for listing_id, gold in labels_by_id.items():
        expected = {}
        for field, value in gold["remark_numeric_gold"].items():
            if gold["structured_numeric_gold"].get(field) is None and value is not None:
                expected[field] = value
        adjusted_labels[listing_id] = {"remark_numeric_gold": expected}
    return _numeric_metrics(predicted_by_id, adjusted_labels, "remark_numeric_gold")


def _text_metrics(predicted_by_id, labels_by_id, error_limit):
    overall = {"tp": 0, "fp": 0, "fn": 0, "exact": 0}
    buckets = {}
    false_positives = []
    false_negatives = []

    for listing_id, gold in labels_by_id.items():
        expected = signal_pairs(gold["text_signal_gold"])
        predicted = signal_pairs(predicted_by_id[listing_id]["text_signals"])
        true_positive = expected & predicted
        false_positive = predicted - expected
        false_negative = expected - predicted

        overall["tp"] += len(true_positive)
        overall["fp"] += len(false_positive)
        overall["fn"] += len(false_negative)
        overall["exact"] += predicted == expected

        for bucket in set(gold["text_signal_gold"]) | set(predicted_by_id[listing_id]["text_signals"]):
            bucket_metrics = buckets.setdefault(
                bucket,
                {"tp": 0, "fp": 0, "fn": 0, "exact": 0, "listings": 0},
            )
            expected_bucket = {pair for pair in expected if pair[0] == bucket}
            predicted_bucket = {pair for pair in predicted if pair[0] == bucket}
            bucket_metrics["tp"] += len(expected_bucket & predicted_bucket)
            bucket_metrics["fp"] += len(predicted_bucket - expected_bucket)
            bucket_metrics["fn"] += len(expected_bucket - predicted_bucket)
            bucket_metrics["exact"] += expected_bucket == predicted_bucket
            bucket_metrics["listings"] += 1

        false_positives.extend(
            {"listing_id": listing_id, "bucket": bucket, "value": value}
            for bucket, value in false_positive
        )
        false_negatives.extend(
            {"listing_id": listing_id, "bucket": bucket, "value": value}
            for bucket, value in false_negative
        )

    return {
        **classification_metrics(overall["tp"], overall["fp"], overall["fn"]),
        "exact_set_accuracy": ratio(overall["exact"], len(labels_by_id)),
        "per_bucket": {
            bucket: {
                **classification_metrics(values["tp"], values["fp"], values["fn"]),
                "exact_set_accuracy": ratio(values["exact"], values["listings"]),
            }
            for bucket, values in sorted(buckets.items())
        },
        "false_positives": sorted(
            false_positives,
            key=lambda item: (item["bucket"], str(item["value"])),
        )[:error_limit],
        "false_negatives": sorted(
            false_negatives,
            key=lambda item: (item["bucket"], str(item["value"])),
        )[:error_limit],
    }


def _keyword_integrity(predicted_by_id):
    valid = 0
    for record in predicted_by_id.values():
        expected = sorted(
            {
                value
                for values in record["text_signals"].values()
                for value in values
                if isinstance(value, str)
            }
        )
        valid += record["keywords"] == expected
    return {"valid_records": valid, "total_records": len(predicted_by_id), "accuracy": ratio(valid, len(predicted_by_id))}


def signal_pairs(signals):
    pairs = set()
    for bucket, values in signals.items():
        for value in values:
            pairs.add((bucket, normalize_value(value)))
    return pairs


def normalize_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number) if number.is_integer() else number
    text = str(value).lower()
    text = re.sub(r"[-_/]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def values_match(actual, expected):
    if actual is None or expected is None:
        return actual is expected
    actual_number = number_value(actual)
    expected_number = number_value(expected)
    if actual_number is not None and expected_number is not None:
        return actual_number == expected_number
    return normalize_value(actual) == normalize_value(expected)


def number_value(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number) if number.is_integer() else number
    if isinstance(value, str):
        try:
            number = float(value.replace(",", "").strip())
        except ValueError:
            return None
        return int(number) if number.is_integer() else number
    return None


def classification_metrics(true_positive, false_positive, false_negative):
    precision = ratio(true_positive, true_positive + false_positive)
    recall = ratio(true_positive, true_positive + false_negative)
    return {
        "precision": precision,
        "recall": recall,
        "f1": ratio(2 * precision * recall, precision + recall),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "support": true_positive + false_negative,
    }


def ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def main():
    args = parse_args()
    labels = load_labels(args.labels)
    records = load_records(args.source, labels)
    predictions = SignalExtractor(taxonomy_path=args.taxonomy).extract_many(records)
    results = evaluate_records(predictions, labels, error_limit=args.error_limit)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(results, indent=2) + "\n")

    structured = results["structured_fields"]
    free_text = results["free_text"]
    print(f"Evaluated {results['listings_evaluated']} listings")
    print(f"Structured field accuracy: {structured['accuracy']:.3f}")
    print(f"Free-text precision/recall/F1: {free_text['precision']:.3f}/{free_text['recall']:.3f}/{free_text['f1']:.3f}")
    print(f"Wrote results to {output_path}")


if __name__ == "__main__":
    main()
