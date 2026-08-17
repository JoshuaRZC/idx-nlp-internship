import argparse
import json
import re
from pathlib import Path

from rouge_score import rouge_scorer


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate generated listing summaries.")
    parser.add_argument("--labels", default="data/processed/listing_summary_eval_labels.json")
    parser.add_argument("--summaries", default="data/processed/listing_summaries.jsonl")
    parser.add_argument("--split", choices=["dev", "test"], default="test")
    parser.add_argument("--output", default="data/processed/listing_summary_eval_results.json")
    return parser.parse_args()


def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return {str(row["listing_id"]): row["summary"] for line in f if (row := json.loads(line))}


def normalize(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def count_text(value):
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def price_text(value):
    return f"{float(value):,.0f}".replace(",", "")


def fact_checks(summary, facts, feature_gold):
    normalized = normalize(summary)
    digits_only = re.sub(r"\D", "", str(summary))
    checks = {}
    if facts.get("price") is not None:
        checks["price"] = price_text(facts["price"]) in digits_only
    if facts.get("beds") is not None and float(facts["beds"]) > 0:
        checks["beds"] = f"{count_text(facts['beds'])} bed" in normalized
    if facts.get("baths") is not None and float(facts["baths"]) > 0:
        checks["baths"] = f"{count_text(facts['baths'])} bath" in normalized
    if facts.get("city"):
        checks["city"] = normalize(facts["city"]) in normalized
    for feature in feature_gold:
        checks[feature] = normalize(feature) in normalized
    return checks


def evaluate_items(items, summaries, split):
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    rows = []
    for item in items:
        if item["split"] != split:
            continue
        summary = summaries.get(str(item["listing_id"]), "")
        score = scorer.score(item["reference_summary"], summary)["rougeL"].fmeasure
        checks = fact_checks(summary, item["facts"], item["feature_gold"])
        rows.append(
            {
                "id": item["id"],
                "listing_id": str(item["listing_id"]),
                "reference_summary": item["reference_summary"],
                "summary": summary,
                "rouge_l": score,
                "fact_checks": checks,
                "fact_coverage": sum(checks.values()) / len(checks) if checks else 1.0,
            }
        )

    return {
        "split": split,
        "listings_evaluated": len(rows),
        "rouge_l": sum(row["rouge_l"] for row in rows) / len(rows) if rows else 0.0,
        "fact_coverage": sum(row["fact_coverage"] for row in rows) / len(rows) if rows else 0.0,
        "rows": rows,
    }


def main():
    args = parse_args()
    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))["items"]
    results = evaluate_items(labels, load_jsonl(args.summaries), args.split)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ROUGE-L: {results['rouge_l']:.3f}")
    print(f"Fact coverage: {results['fact_coverage']:.3f}")


if __name__ == "__main__":
    main()
