import argparse
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.query_parser import QueryParser  # noqa: E402


KEY_MAP = {
    "max_price": "price_max",
    "min_price": "price_min",
}

VALUE_ALIASES = {
    "family homes": "house",
    "house": "house",
    "houses": "house",
    "single family homes": "single family",
    "single family home": "single family",
    "single family": "single family",
    "townhomes": "townhouse",
    "townhome": "townhouse",
    "condos": "condo",
    "condominiums": "condo",
    "ocean views": "ocean view",
    "city lights views": "city lights view",
    "tennis courts": "tennis court",
    "fixer": "fixer upper",
    "project": "project",
    "barbecue": "barbecue",
}


def load_queries(path):
    with Path(path).open() as f:
        return json.load(f)


def normalize_expected(entities):
    normalized = {}
    for key, value in entities.items():
        key = KEY_MAP.get(key, key)
        normalized[key] = normalize_value(value)
    _move_fireplace_to_interior_features(normalized)
    return normalized


def _move_fireplace_to_interior_features(filters):
    amenities = filters.get("amenities")
    if not isinstance(amenities, list) or "fireplace" not in amenities:
        return

    filters["amenities"] = [value for value in amenities if value != "fireplace"]
    if not filters["amenities"]:
        del filters["amenities"]

    interior_features = filters.setdefault("interior_features", [])
    if not isinstance(interior_features, list):
        interior_features = [interior_features]
    filters["interior_features"] = sorted(set(interior_features + ["fireplace"]))


def normalize_filters(filters):
    return {
        KEY_MAP.get(key, key): normalize_value(value)
        for key, value in filters.items()
    }


def split_expected(entities, parser):
    expected = normalize_expected(entities)
    hard, soft = parser.split_filters(expected)
    return normalize_filters(hard), normalize_filters(soft)


def normalize_value(value):
    if isinstance(value, list):
        return sorted(normalize_scalar(item) for item in value)
    return normalize_scalar(value)


def normalize_scalar(value):
    if isinstance(value, str):
        value = value.strip().lower()
        return VALUE_ALIASES.get(value, value)
    return value


def score_field(expected, predicted):
    expected = normalize_value(expected)
    predicted = normalize_value(predicted)

    if isinstance(expected, list):
        predicted_values = set(predicted if isinstance(predicted, list) else [predicted])
        return set(expected).issubset(predicted_values)
    return expected == predicted


def evaluate(queries, parser, include_soft_signals=False):
    total_expected_fields = 0
    matched_expected_fields = 0
    exact_queries = 0
    hard_exact_queries = 0
    soft_exact_queries = 0
    missed = Counter()
    extra = Counter()
    hard_extra = Counter()
    soft_extra = Counter()
    rows = []

    for item in queries:
        expected = normalize_expected(item["entities"])
        expected_hard, expected_soft = split_expected(item["entities"], parser)

        parsed = parser.parse(item["query"])
        predicted = normalize_filters(parsed["filters"])
        predicted_hard = normalize_filters(parsed["hard_filters"])
        predicted_soft = normalize_filters(parsed["soft_signals"])

        expected_fields_matched = True
        for key, expected_value in expected.items():
            total_expected_fields += 1
            if key in predicted and score_field(expected_value, predicted[key]):
                matched_expected_fields += 1
            else:
                expected_fields_matched = False
                missed[key] += 1

        for key in predicted:
            if key not in expected:
                extra[key] += 1
        for key in predicted_hard:
            if key not in expected_hard:
                hard_extra[key] += 1
        for key in predicted_soft:
            if key not in expected_soft:
                soft_extra[key] += 1

        full_filter_exact_match = predicted == expected
        hard_filter_exact_match = predicted_hard == expected_hard
        soft_signal_exact_match = predicted_soft == expected_soft
        if full_filter_exact_match:
            exact_queries += 1
        if hard_filter_exact_match:
            hard_exact_queries += 1
        if soft_signal_exact_match:
            soft_exact_queries += 1

        rows.append(
            {
                "id": item["id"],
                "query": item["query"],
                "expected": expected,
                "predicted": predicted,
                "expected_hard": expected_hard,
                "predicted_hard": predicted_hard,
                "expected_soft": expected_soft,
                "predicted_soft": predicted_soft,
                "expected_fields_matched": expected_fields_matched,
                "full_filter_exact_match": full_filter_exact_match,
                "hard_filter_exact_match": hard_filter_exact_match,
                "soft_signal_exact_match": soft_signal_exact_match,
            }
        )

    return {
        "total_queries": len(queries),
        "total_expected_fields": total_expected_fields,
        "matched_expected_fields": matched_expected_fields,
        "full_filter_exact_match_rate": exact_queries / len(queries) if queries else 0,
        "hard_filter_exact_match_rate": hard_exact_queries / len(queries) if queries else 0,
        "soft_signal_exact_match_rate": soft_exact_queries / len(queries) if queries else 0,
        "missed_fields": dict(missed.most_common()),
        "extra_fields": dict(extra.most_common()),
        "hard_extra_fields": dict(hard_extra.most_common()),
        "soft_extra_fields": dict(soft_extra.most_common()),
        "include_soft_signals": include_soft_signals,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default="data/processed/sample_queries.json")
    parser.add_argument("--error-limit", type=int, default=20)
    parser.add_argument("--include-soft-signals", action="store_true")
    args = parser.parse_args()

    query_parser = QueryParser()
    report = evaluate(
        load_queries(args.queries),
        query_parser,
        include_soft_signals=args.include_soft_signals,
    )

    print(f"Queries: {report['total_queries']}")
    print(
        f"Expected fields matched: "
        f"{report['matched_expected_fields']}/{report['total_expected_fields']}"
    )
    print(f"Hard-filter exact match rate: {report['hard_filter_exact_match_rate']:.3f}")
    if args.include_soft_signals:
        print(f"Soft-signal exact match rate: {report['soft_signal_exact_match_rate']:.3f}")
        print(f"Full-filter exact match rate: {report['full_filter_exact_match_rate']:.3f}")
    print("Missed fields:")
    for key, count in report["missed_fields"].items():
        print(f"  {key}: {count}")
    print("Hard-filter extra fields:")
    for key, count in report["hard_extra_fields"].items():
        print(f"  {key}: {count}")
    if args.include_soft_signals:
        print("Full extra fields:")
        for key, count in report["extra_fields"].items():
            print(f"  {key}: {count}")
        print("Soft-signal extra fields:")
        for key, count in report["soft_extra_fields"].items():
            print(f"  {key}: {count}")

    failure_key = "full_filter_exact_match" if args.include_soft_signals else "hard_filter_exact_match"
    failures = [row for row in report["rows"] if not row[failure_key]]
    if failures and args.error_limit:
        print("\nExamples:")
        for row in failures[: args.error_limit]:
            print(f"- {row['id']}: {row['query']}")
            print(f"  expected: {row['expected']}")
            print(f"  predicted: {row['predicted']}")
            print(f"  hard expected: {row['expected_hard']}")
            print(f"  hard predicted: {row['predicted_hard']}")
            print(f"  soft expected: {row['expected_soft']}")
            print(f"  soft predicted: {row['predicted_soft']}")


if __name__ == "__main__":
    main()
