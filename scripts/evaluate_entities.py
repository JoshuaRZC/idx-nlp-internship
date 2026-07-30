import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import spacy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.entity_extractor import EntityExtractor  # noqa: E402


class SpacyNerExtractor:
    def __init__(self, model_path):
        self.nlp = spacy.load(model_path)

    def extract(self, text):
        doc = self.nlp(text)
        return [
            {
                "label": ent.label_,
                "value": ent.text.strip().lower(),
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "method": "ner",
                "source": str(self.nlp.meta.get("name", "spacy_ner")),
            }
            for ent in doc.ents
        ]

    def extract_all(self, text):
        return self.extract(text)


def load_gold(path):
    with Path(path).open() as f:
        data = json.load(f)
    return data["items"]


def entity_key(entity, match_mode):
    key = [entity["label"]]

    if match_mode in {"span", "strict"}:
        key.extend([entity["start"], entity["end"]])

    if match_mode in {"value", "strict"}:
        key.append(value_key(entity.get("value")))

    return tuple(key)


def value_key(value):
    if isinstance(value, str):
        return value.strip().lower()
    return json.dumps(value, sort_keys=True)


def score_entities(gold_entities, predicted_entities, match_mode):
    if match_mode == "overlap":
        return score_overlap_entities(gold_entities, predicted_entities)

    gold = Counter(entity_key(entity, match_mode) for entity in gold_entities)
    predicted = Counter(entity_key(entity, match_mode) for entity in predicted_entities)

    true_positive = sum((gold & predicted).values())
    false_positive = sum((predicted - gold).values())
    false_negative = sum((gold - predicted).values())

    return true_positive, false_positive, false_negative


def score_overlap_entities(gold_entities, predicted_entities):
    matched_gold = set()
    true_positive = 0

    for predicted in predicted_entities:
        match_index = first_overlap_match(predicted, gold_entities, matched_gold)
        if match_index is None:
            continue
        matched_gold.add(match_index)
        true_positive += 1

    false_positive = len(predicted_entities) - true_positive
    false_negative = len(gold_entities) - true_positive
    return true_positive, false_positive, false_negative


def first_overlap_match(predicted, gold_entities, matched_gold):
    for index, gold in enumerate(gold_entities):
        if index in matched_gold:
            continue
        if predicted["label"] != gold["label"]:
            continue
        if value_key(predicted.get("value")) != value_key(gold.get("value")):
            continue
        if predicted["start"] < gold["end"] and gold["start"] < predicted["end"]:
            return index
    return None


def metric_row(true_positive, false_positive, false_negative):
    precision = safe_divide(true_positive, true_positive + false_positive)
    recall = safe_divide(true_positive, true_positive + false_negative)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    return {
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def safe_divide(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def evaluate(items, extractor, match_mode):
    overall_counts = [0, 0, 0]
    per_label_counts = defaultdict(lambda: [0, 0, 0])
    false_positives = []
    false_negatives = []

    for item in items:
        gold_entities = item["entities"]
        predicted_entities = extractor.extract_all(item["text"])

        true_positive, false_positive, false_negative = score_entities(
            gold_entities,
            predicted_entities,
            match_mode,
        )
        overall_counts[0] += true_positive
        overall_counts[1] += false_positive
        overall_counts[2] += false_negative

        labels = sorted(
            {entity["label"] for entity in gold_entities}
            | {entity["label"] for entity in predicted_entities}
        )
        for label in labels:
            label_gold = [entity for entity in gold_entities if entity["label"] == label]
            label_predicted = [entity for entity in predicted_entities if entity["label"] == label]
            counts = score_entities(label_gold, label_predicted, match_mode)
            per_label_counts[label][0] += counts[0]
            per_label_counts[label][1] += counts[1]
            per_label_counts[label][2] += counts[2]

        false_positives.extend(
            collect_errors(item, gold_entities, predicted_entities, match_mode, predicted=True)
        )
        false_negatives.extend(
            collect_errors(item, gold_entities, predicted_entities, match_mode, predicted=False)
        )

    per_label = {
        label: metric_row(*counts)
        for label, counts in sorted(per_label_counts.items())
    }

    return {
        "overall": metric_row(*overall_counts),
        "per_label": per_label,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def collect_errors(item, gold_entities, predicted_entities, match_mode, predicted):
    if match_mode == "overlap":
        return collect_overlap_errors(item, gold_entities, predicted_entities, predicted)

    gold_keys = Counter(entity_key(entity, match_mode) for entity in gold_entities)
    predicted_keys = Counter(entity_key(entity, match_mode) for entity in predicted_entities)

    if predicted:
        misses = predicted_keys - gold_keys
        source_entities = predicted_entities
        error_type = "false_positive"
    else:
        misses = gold_keys - predicted_keys
        source_entities = gold_entities
        error_type = "false_negative"

    errors = []
    remaining = Counter(misses)
    for entity in source_entities:
        key = entity_key(entity, match_mode)
        if remaining[key] <= 0:
            continue
        remaining[key] -= 1
        errors.append(
            {
                "type": error_type,
                "item_id": item["id"],
                "listing_id": item.get("listing_id"),
                "label": entity["label"],
                "value": entity.get("value"),
                "text": entity["text"],
                "start": entity["start"],
                "end": entity["end"],
                "context": item["text"],
            }
        )
    return errors


def collect_overlap_errors(item, gold_entities, predicted_entities, predicted):
    matched_gold = set()
    matched_predicted = set()

    for pred_index, predicted_entity in enumerate(predicted_entities):
        gold_index = first_overlap_match(predicted_entity, gold_entities, matched_gold)
        if gold_index is None:
            continue
        matched_predicted.add(pred_index)
        matched_gold.add(gold_index)

    if predicted:
        source_entities = [
            entity for index, entity in enumerate(predicted_entities)
            if index not in matched_predicted
        ]
        error_type = "false_positive"
    else:
        source_entities = [
            entity for index, entity in enumerate(gold_entities)
            if index not in matched_gold
        ]
        error_type = "false_negative"

    return [
        {
            "type": error_type,
            "item_id": item["id"],
            "listing_id": item.get("listing_id"),
            "label": entity["label"],
            "value": entity.get("value"),
            "text": entity["text"],
            "start": entity["start"],
            "end": entity["end"],
            "context": item["text"],
        }
        for entity in source_entities
    ]


def print_report(results, error_limit):
    print("Overall")
    print_metric(results["overall"])

    print("\nPer label")
    for label, row in results["per_label"].items():
        print(
            f"{label:24} "
            f"P={row['precision']:.3f} "
            f"R={row['recall']:.3f} "
            f"F1={row['f1']:.3f} "
            f"TP={row['tp']} FP={row['fp']} FN={row['fn']}"
        )

    print_errors("False positives", results["false_positives"], error_limit)
    print_errors("False negatives", results["false_negatives"], error_limit)


def print_metric(row):
    print(f"precision: {row['precision']:.3f}")
    print(f"recall:    {row['recall']:.3f}")
    print(f"f1:        {row['f1']:.3f}")
    print(f"tp/fp/fn:  {row['tp']}/{row['fp']}/{row['fn']}")


def print_errors(title, errors, limit):
    print(f"\n{title}")
    for error in errors[:limit]:
        print(
            f"- {error['item_id']} "
            f"{error['label']}={error['value']!r} "
            f"text={error['text']!r} "
            f"span=({error['start']}, {error['end']})"
        )


def save_results(results, path):
    payload = {
        "overall": results["overall"],
        "per_label": results["per_label"],
        "false_positives": results["false_positives"],
        "false_negatives": results["false_negatives"],
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate entity extraction against gold labels.")
    parser.add_argument(
        "--labels",
        default="data/processed/entity_eval_labels.json",
        help="Path to the gold entity label file.",
    )
    parser.add_argument(
        "--taxonomy",
        default="data/processed/taxonomy.json",
        help="Path to taxonomy.json.",
    )
    parser.add_argument(
        "--system",
        choices=["rule", "ner", "hybrid"],
        default="rule",
        help="Extraction system to evaluate.",
    )
    parser.add_argument(
        "--ner-model",
        help="Path to a saved spaCy NER model. Required for ner or hybrid.",
    )
    parser.add_argument(
        "--match-mode",
        choices=["strict", "span", "value", "overlap"],
        default="strict",
        help=(
            "strict = label + span + value; span = label + span; "
            "value = label + value; overlap = label + value + overlapping span."
        ),
    )
    parser.add_argument(
        "--error-limit",
        type=int,
        default=20,
        help="Number of false positives/negatives to print.",
    )
    parser.add_argument(
        "--output",
        help="Optional path for full evaluation details as JSON.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    items = load_gold(args.labels)
    if args.system == "rule":
        extractor = EntityExtractor(taxonomy_path=args.taxonomy)
    elif args.system == "ner":
        if not args.ner_model:
            raise SystemExit("--ner-model is required when --system=ner")
        extractor = SpacyNerExtractor(args.ner_model)
    else:
        if not args.ner_model:
            raise SystemExit("--ner-model is required when --system=hybrid")
        extractor = EntityExtractor(
            taxonomy_path=args.taxonomy,
            ner_model=SpacyNerExtractor(args.ner_model),
        )
    results = evaluate(items, extractor, args.match_mode)

    print_report(results, args.error_limit)
    if args.output:
        save_results(results, args.output)


if __name__ == "__main__":
    main()
