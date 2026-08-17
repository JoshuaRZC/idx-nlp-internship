import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.compliance_checker import ComplianceChecker  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate the Fair Housing compliance checker.")
    parser.add_argument("--labels", default="data/processed/compliance_eval_labels.json")
    parser.add_argument("--output", default="data/processed/compliance_eval_results.json")
    parser.add_argument("--error-limit", type=int, default=20)
    return parser.parse_args()


def load_items(path):
    items = json.loads(Path(path).read_text(encoding="utf-8"))["items"]
    pending = [item["id"] for item in items if item.get("annotation_status") != "complete"]
    if pending:
        raise ValueError(f"{len(pending)} label items still require review.")
    return items


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def expected_classes(item, rules_by_id):
    return {
        rules_by_id[finding["rule_id"]].protected_class
        for finding in item["expected_findings"]
        if finding["rule_id"] in rules_by_id
    }


def evaluate_items(items, checker=None, error_limit=20):
    checker = checker or ComplianceChecker()
    rules_by_id = {rule.rule_id: rule for rule in checker.rules}
    status_correct = 0
    blocked_total = 0
    blocked_detected = 0
    actionable_total = 0
    actionable_correct = 0
    clean_total = 0
    clean_alerts = 0
    class_counts = defaultdict(lambda: {"expected": 0, "detected": 0})
    errors = []
    matrix = Counter()

    for item in items:
        result = checker.check_listing(item["text"])
        expected_status = item["expected_status"]
        predicted_status = result["status"]
        matrix[(expected_status, predicted_status)] += 1
        status_correct += expected_status == predicted_status

        if expected_status == "blocked":
            blocked_total += 1
            blocked_detected += predicted_status == "blocked"

        if predicted_status != "pass":
            actionable_total += 1
            actionable_correct += expected_status != "pass"

        if expected_status == "pass":
            clean_total += 1
            clean_alerts += predicted_status != "pass"

        predicted_classes = {finding["protected_class"] for finding in result["findings"]}
        for protected_class in expected_classes(item, rules_by_id):
            class_counts[protected_class]["expected"] += 1
            class_counts[protected_class]["detected"] += protected_class in predicted_classes

        if expected_status != predicted_status and len(errors) < error_limit:
            errors.append(
                {
                    "id": item["id"],
                    "source": item["source"],
                    "text": item["text"],
                    "expected_status": expected_status,
                    "predicted_status": predicted_status,
                    "findings": result["findings"],
                }
            )

    statuses = ("pass", "review", "blocked")
    results = {
        "items_evaluated": len(items),
        "known_violation_recall": ratio(blocked_detected, blocked_total),
        "actionable_alert_precision": ratio(actionable_correct, actionable_total),
        "status_accuracy": ratio(status_correct, len(items)),
        "clean_listing_false_positive_rate": ratio(clean_alerts, clean_total),
        "per_protected_class_recall": {
            name: {
                "expected": values["expected"],
                "detected": values["detected"],
                "recall": ratio(values["detected"], values["expected"]),
            }
            for name, values in sorted(class_counts.items())
        },
        "status_confusion_matrix": {
            "labels": list(statuses),
            "values": [[matrix[(expected, predicted)] for predicted in statuses] for expected in statuses],
        },
        "errors": errors,
    }
    return results


def main():
    args = parse_args()
    results = evaluate_items(load_items(args.labels), error_limit=args.error_limit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Evaluated {results['items_evaluated']} items")
    print(f"Known-violation recall: {results['known_violation_recall']:.3f}")
    print(f"Actionable-alert precision: {results['actionable_alert_precision']:.3f}")
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
