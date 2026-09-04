from types import SimpleNamespace

import pytest

from scripts.build_search_relevance_pool import build_pool
from scripts.build_search_relevance_delta_pool import build_delta_pool
from scripts.evaluate_search_relevance import (
    evaluate_items,
    ndcg_at_k,
    reciprocal_rank,
    validate_manifest,
)
from scripts.finalize_search_relevance_labels import finalize
from scripts.merge_search_relevance_delta_qrels import merge_qrels


class StubService:
    def __init__(self, results, snapshot_id="snapshot-a"):
        self.snapshot = SimpleNamespace(snapshot_id=snapshot_id)
        self.results = results

    def search_experiment(self, query, variant, top_k):
        rows = self.results[variant, query][:top_k]
        return {
            "ok": True,
            "message": "Results found.",
            "results": rows,
            "meta": {
                "effective_sort": "relevance",
                "timings_ms": {"total": 12.5},
                "eligible_count": 10,
                "candidate_counts": {"rrf_union": 8},
                "degraded_components": [],
            },
        }


def query_dataset():
    return {
        "snapshot_id": "snapshot-a",
        "items": [
            {"id": "query_dev", "query": "pool homes", "split": "dev"},
            {"id": "query_test", "query": "fireplace homes", "split": "test"},
        ],
    }


def row(listing_id):
    return {
        "listing_id": listing_id,
        "city": "Galt",
        "price": 500000,
        "beds": 3,
        "baths": 2,
        "sqft": 1500,
        "remarks_cleaned": f"listing {listing_id}",
        "score": 0.1,
        "summary": "Do not expose this in the annotation pool.",
        "source_ranks": {"dense": 1},
    }


def stub_service():
    results = {}
    for variant in ("dense_only",):
        results[variant, "pool homes"] = [row(value) for value in ["a", "b", "c", "d", "e"]]
        results[variant, "fireplace homes"] = [row(value) for value in ["f", "g", "h", "i", "j"]]
    return StubService(results)


def qrels():
    grades = {
        "query_dev": {"a": 3, "b": 2, "c": 1, "d": 0, "e": 0},
        "query_test": {"f": 0, "g": 0, "h": 2, "i": 1, "j": 3},
    }
    return [
        {
            "query_id": query_id,
            "listing_id": listing_id,
            "snapshot_id": "snapshot-a",
            "annotation_status": "complete",
            "relevance_grade": grade,
        }
        for query_id, values in grades.items()
        for listing_id, grade in values.items()
    ]


def test_evaluation_reports_dev_and_test_metrics():
    report = evaluate_items(stub_service(), query_dataset(), qrels(), variants=("dense_only",))

    dev = report["variants"]["dense_only"]["dev"]
    test = report["variants"]["dense_only"]["test"]
    assert dev["precision_at_5"] == 0.4
    assert dev["mrr_at_5"] == 1.0
    assert test["precision_at_5"] == 0.4
    assert test["mrr_at_5"] == pytest.approx(1 / 3)
    assert dev["latency_ms"] == {"mean": 12.5, "p50": 12.5, "p95": 12.5}
    assert dev["candidate_counts"]["rrf_union"]["mean"] == 8
    assert ndcg_at_k([3, 2, 1, 0, 0], [3, 2, 1, 0, 0]) == 1.0
    assert reciprocal_rank([0, 1, 2]) == pytest.approx(1 / 3)


def test_evaluation_rejects_unjudged_top_five_result():
    incomplete = [item for item in qrels() if not (item["query_id"] == "query_dev" and item["listing_id"] == "e")]

    with pytest.raises(ValueError, match="Unjudged top-5"):
        evaluate_items(stub_service(), query_dataset(), incomplete, variants=("dense_only",))


def test_evaluation_rejects_snapshot_mismatch():
    with pytest.raises(ValueError, match="Active snapshot"):
        evaluate_items(StubService({}, snapshot_id="snapshot-b"), query_dataset(), qrels(), variants=())


def test_evaluation_can_limit_results_to_dev_queries():
    report = evaluate_items(
        stub_service(),
        query_dataset(),
        qrels(),
        variants=("dense_only",),
        splits=("dev",),
    )

    assert report["splits"] == ["dev"]
    assert set(report["variants"]["dense_only"]) == {"dev"}


def test_manifest_rejects_changed_files(tmp_path):
    queries = tmp_path / "queries.json"
    qrels_path = tmp_path / "qrels.jsonl"
    queries.write_text('{"snapshot_id": "snapshot-a", "items": []}')
    qrels_path.write_text("")
    manifest = {
        "snapshot_id": "snapshot-a",
        "queries_sha256": "not-the-right-hash",
        "qrels_sha256": "not-the-right-hash",
    }

    with pytest.raises(ValueError, match="Query dataset differs"):
        validate_manifest(manifest, queries, qrels_path, "snapshot-a")


def test_delta_pool_contains_only_new_blinded_candidates():
    labels = [item for item in qrels() if not (item["query_id"] == "query_dev" and item["listing_id"] == "a")]

    pool = build_delta_pool(
        stub_service(),
        query_dataset(),
        labels,
        variant="dense_only",
        split="dev",
    )

    assert len(pool) == 1
    assert pool[0]["listing_id"] == "a"
    assert pool[0]["annotation_status"] == "pending"
    assert "score" not in pool[0]
    assert "summary" not in pool[0]


def test_delta_qrels_merge_requires_a_complete_non_overlapping_grade_map():
    base = [
        {
            "query_id": "query_dev",
            "listing_id": "a",
            "snapshot_id": "snapshot-a",
            "annotation_status": "complete",
            "relevance_grade": 3,
        }
    ]
    pool = [{"query_id": "query_dev", "listing_id": "b", "snapshot_id": "snapshot-a"}]
    grade_map = {"snapshot_id": "snapshot-a", "grades": {"query_dev": {"b": 2}}}

    merged = merge_qrels(base, pool, grade_map)

    assert [item["listing_id"] for item in merged] == ["a", "b"]
    with pytest.raises(ValueError, match="exactly match"):
        merge_qrels(base, pool, {"snapshot_id": "snapshot-a", "grades": {"query_dev": {}}})


def test_pool_hides_scores_summaries_and_sources():
    dataset = {"snapshot_id": "snapshot-a", "items": [query_dataset()["items"][0]]}
    service = stub_service()
    pool = build_pool(service, dataset, variants=("dense_only",))

    assert len(pool) == 5
    assert all(item["annotation_status"] == "pending" for item in pool)
    assert all(item["relevance_grade"] is None for item in pool)
    assert all("score" not in item and "summary" not in item and "source_ranks" not in item for item in pool)


def test_finalizer_requires_one_complete_grade_per_pool_candidate():
    pool = [
        {"query_id": "query_dev", "listing_id": "a", "snapshot_id": "snapshot-a"},
        {"query_id": "query_dev", "listing_id": "b", "snapshot_id": "snapshot-a"},
    ]
    grade_map = {"snapshot_id": "snapshot-a", "grades": {"query_dev": {"a": 3, "b": 1}}}

    labels = finalize(pool, grade_map)

    assert [item["relevance_grade"] for item in labels] == [3, 1]
    with pytest.raises(ValueError, match="Grade map mismatch"):
        finalize(pool, {"snapshot_id": "snapshot-a", "grades": {"query_dev": {"a": 3}}})
