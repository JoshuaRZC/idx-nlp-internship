"""Evaluate Search Service variants against manually judged pooled relevance labels."""

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.real_estate_nlp.search_service import SearchService  # noqa: E402


EVALUATION_VARIANTS = (
    "bm25_only",
    "dense_only",
    "dense_signal",
    "dense_bm25_signal_rrf",
    "hybrid_cross_encoder",
)
RELEVANT_GRADE = 2
VALID_GRADES = {0, 1, 2, 3}


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate Search Service relevance variants.")
    parser.add_argument("--queries", default="data/processed/search_relevance_queries.json")
    parser.add_argument("--qrels", default="data/processed/search_relevance_qrels.jsonl")
    parser.add_argument("--manifest", default="data/processed/search_relevance_manifest.json")
    parser.add_argument("--output", default="data/processed/search_relevance_dev_results.json")
    parser.add_argument("--search-root", default="data/models/search")
    retrieval_mode = parser.add_mutually_exclusive_group()
    retrieval_mode.add_argument(
        "--parallel-retrieval",
        dest="parallel_retrieval",
        action="store_true",
        help="Run dense, BM25, and signal matching concurrently after hard filtering.",
    )
    retrieval_mode.add_argument(
        "--serial-retrieval",
        dest="parallel_retrieval",
        action="store_false",
        help="Run retrieval sources one at a time for latency comparison.",
    )
    parser.set_defaults(parallel_retrieval=True)
    parser.add_argument(
        "--retrieval-workers",
        type=int,
        default=2,
        help="Maximum retrieval tasks allowed to run at once when parallel retrieval is enabled.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--variants",
        choices=EVALUATION_VARIANTS,
        nargs="+",
        default=EVALUATION_VARIANTS,
        help="Search variants to evaluate. Defaults to every internal variant.",
    )
    parser.add_argument(
        "--splits",
        choices=("dev", "test"),
        nargs="+",
        default=("dev",),
        help="Dataset splits to evaluate. Defaults to dev; test must be requested explicitly.",
    )
    return parser.parse_args()


def load_query_dataset(path):
    payload = json.loads(Path(path).read_text())
    if not payload.get("snapshot_id"):
        raise ValueError("Query dataset must include snapshot_id.")
    if not isinstance(payload.get("items"), list):
        raise ValueError("Query dataset must include an items list.")
    return payload


def load_qrels(path):
    items = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                items.append(json.loads(line))
    return items


def load_manifest(path):
    manifest = json.loads(Path(path).read_text())
    required = {"snapshot_id", "queries_sha256", "qrels_sha256"}
    missing = required - manifest.keys()
    if missing:
        raise ValueError(f"Evaluation manifest is missing: {', '.join(sorted(missing))}.")
    return manifest


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_manifest(manifest, queries_path, qrels_path, snapshot_id):
    if manifest["snapshot_id"] != snapshot_id:
        raise ValueError("Active snapshot does not match the evaluation manifest.")
    if manifest["queries_sha256"] != file_sha256(queries_path):
        raise ValueError("Query dataset differs from the frozen evaluation manifest.")
    if manifest["qrels_sha256"] != file_sha256(qrels_path):
        raise ValueError("Qrels differ from the frozen evaluation manifest.")


def validate_labels(query_dataset, qrels, snapshot_id):
    if query_dataset["snapshot_id"] != snapshot_id:
        raise ValueError("Active snapshot does not match the query dataset.")

    query_ids = {item["id"] for item in query_dataset["items"]}
    if len(query_ids) != len(query_dataset["items"]):
        raise ValueError("Query dataset contains duplicate IDs.")

    labels = {}
    for item in qrels:
        key = (item.get("query_id"), str(item.get("listing_id")))
        if key[0] not in query_ids:
            raise ValueError(f"Unknown query ID in qrels: {key[0]}")
        if item.get("snapshot_id") != snapshot_id:
            raise ValueError(f"Snapshot mismatch in qrels for {key[0]} / {key[1]}.")
        if item.get("annotation_status") != "complete":
            raise ValueError(f"Incomplete annotation for {key[0]} / {key[1]}.")
        if item.get("relevance_grade") not in VALID_GRADES:
            raise ValueError(f"Invalid relevance grade for {key[0]} / {key[1]}.")
        if key in labels:
            raise ValueError(f"Duplicate qrel for {key[0]} / {key[1]}.")
        labels[key] = item["relevance_grade"]
    return labels


def evaluate_items(service, query_dataset, qrels, top_k=5, variants=EVALUATION_VARIANTS, splits=None):
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    labels = validate_labels(query_dataset, qrels, service.snapshot.snapshot_id)
    by_query = defaultdict(list)
    for (query_id, _), grade in labels.items():
        by_query[query_id].append(grade)

    selected_splits = tuple(splits or ("dev", "test"))
    invalid_splits = set(selected_splits) - {"dev", "test"}
    if invalid_splits:
        raise ValueError(f"Unsupported evaluation splits: {sorted(invalid_splits)}")
    items = [item for item in query_dataset["items"] if item["split"] in selected_splits]
    if not items:
        raise ValueError("No query items match the requested evaluation splits.")

    report = {
        "snapshot_id": service.snapshot.snapshot_id,
        "top_k": top_k,
        "relevant_grade_threshold": RELEVANT_GRADE,
        "parallel_retrieval": getattr(service, "parallel_retrieval", False),
        "retrieval_workers": getattr(service, "retrieval_workers", None),
        "splits": list(selected_splits),
        "variants": {},
    }
    for variant in variants:
        rows = []
        for query_item in items:
            response = service.search_experiment(query_item["query"], variant, top_k=top_k)
            if not response["ok"]:
                raise ValueError(f"Query {query_item['id']} is not answerable: {response['message']}")
            if response["meta"].get("effective_sort") != "relevance":
                raise ValueError(f"Query {query_item['id']} is not a relevance query.")
            if len(response["results"]) != top_k:
                raise ValueError(f"Query {query_item['id']} returned fewer than {top_k} results for {variant}.")

            result_ids = [str(item["listing_id"]) for item in response["results"]]
            missing = [listing_id for listing_id in result_ids if (query_item["id"], listing_id) not in labels]
            if missing:
                raise ValueError(
                    f"Unjudged top-{top_k} result for {variant} / {query_item['id']}: {', '.join(missing)}"
                )

            grades = [labels[(query_item["id"], listing_id)] for listing_id in result_ids]
            ideal = sorted(by_query[query_item["id"]], reverse=True)[:top_k]
            rows.append(
                {
                    "query_id": query_item["id"],
                    "split": query_item["split"],
                    "precision_at_5": precision_at_k(grades, top_k),
                    "ndcg_at_5": ndcg_at_k(grades, ideal),
                    "mrr_at_5": reciprocal_rank(grades),
                    "grades": grades,
                    "listing_ids": result_ids,
                    "timings_ms": response["meta"].get("timings_ms", {}),
                    "eligible_count": response["meta"].get("eligible_count"),
                    "candidate_counts": response["meta"].get("candidate_counts", {}),
                    "degraded_components": response["meta"].get("degraded_components", []),
                }
            )
        report["variants"][variant] = summarize_rows(rows, selected_splits)
    return report


def precision_at_k(grades, top_k):
    return sum(grade >= RELEVANT_GRADE for grade in grades[:top_k]) / top_k


def reciprocal_rank(grades):
    for rank, grade in enumerate(grades, start=1):
        if grade >= RELEVANT_GRADE:
            return 1 / rank
    return 0.0


def ndcg_at_k(grades, ideal_grades):
    actual = dcg(grades)
    ideal = dcg(ideal_grades)
    return actual / ideal if ideal else 0.0


def dcg(grades):
    return sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades, start=1))


def summarize_rows(rows, splits=("dev", "test")):
    by_split = {}
    for split in splits:
        split_rows = [row for row in rows if row["split"] == split]
        if not split_rows:
            continue
        by_split[split] = {
            "queries_evaluated": len(split_rows),
            "precision_at_5": mean(row["precision_at_5"] for row in split_rows),
            "ndcg_at_5": mean(row["ndcg_at_5"] for row in split_rows),
            "mrr_at_5": mean(row["mrr_at_5"] for row in split_rows),
            "latency_ms": summarize_measurements(
                [row["timings_ms"]["total"] for row in split_rows if "total" in row["timings_ms"]]
            ),
            "component_latency_ms": summarize_components(split_rows, "timings_ms"),
            "candidate_counts": summarize_components(split_rows, "candidate_counts"),
            "degraded_response_rate": mean(bool(row["degraded_components"]) for row in split_rows),
            "per_query": split_rows,
        }
    return by_split


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def summarize_measurements(values):
    values = sorted(values)
    if not values:
        return {}
    return {
        "mean": mean(values),
        "p50": percentile(values, 0.5),
        "p95": percentile(values, 0.95),
    }


def percentile(values, fraction):
    index = max(0, math.ceil(len(values) * fraction) - 1)
    return values[index]


def summarize_components(rows, key):
    names = {name for row in rows for name in row[key]}
    return {
        name: summarize_measurements([row[key][name] for row in rows if name in row[key]])
        for name in sorted(names)
    }


def main():
    args = parse_args()
    query_dataset = load_query_dataset(args.queries)
    qrels = load_qrels(args.qrels)
    service = SearchService.from_active_snapshot(
        search_root=args.search_root,
        enable_cross_encoder=True,
        parallel_retrieval=args.parallel_retrieval,
        retrieval_workers=args.retrieval_workers,
    )
    service.warm_up(include_cross_encoder=True)
    validate_manifest(load_manifest(args.manifest), args.queries, args.qrels, service.snapshot.snapshot_id)
    report = evaluate_items(
        service,
        query_dataset,
        qrels,
        args.top_k,
        variants=args.variants,
        splits=args.splits,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for variant, splits in report["variants"].items():
        for split, values in splits.items():
            print(
                f"{variant} [{split}] "
                f"P@5={values['precision_at_5']:.3f} "
                f"NDCG@5={values['ndcg_at_5']:.3f} "
                f"MRR@5={values['mrr_at_5']:.3f} "
                f"P50={values['latency_ms'].get('p50', 0):.1f}ms "
                f"P95={values['latency_ms'].get('p95', 0):.1f}ms"
            )
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
