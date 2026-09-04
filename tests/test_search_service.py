import json
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from src.real_estate_nlp.keyword_search import BM25Searcher
from src.real_estate_nlp.listing_repository import ListingRepository
from src.real_estate_nlp.query_parser import QueryParser
from src.real_estate_nlp.schema_validator import SchemaValidator
from src.real_estate_nlp.search_service import CrossEncoderReranker, SearchService, SearchUnavailableError
from src.real_estate_nlp.search_snapshot import SearchSnapshot, SearchSnapshotBuilder, read_jsonl
from src.real_estate_nlp.semantic_search import SemanticSearcher
from src.real_estate_nlp.signal_search import SignalSearcher


class FakeEmbeddingModel:
    def encode(self, texts, **_kwargs):
        vectors = []
        for text in texts:
            text = text.lower()
            vectors.append(["pool" in text, "fireplace" in text, 1])
        return np.asarray(vectors, dtype="float32")


class BrokenEmbeddingModel:
    def encode(self, *_args, **_kwargs):
        raise RuntimeError("embedding model unavailable")


class FakeComplianceChecker:
    rule_version = "test-rules"

    def check_listing(self, text):
        status = "blocked" if "restricted" in str(text).lower() else "pass"
        return {
            "status": status,
            "can_publish": status == "pass",
            "rule_version": self.rule_version,
            "findings": [] if status == "pass" else [{"rule_id": "test"}],
        }


class FakeSignalExtractor:
    def extract_many(self, records):
        output = []
        for record in records:
            text = record["remarks_cleaned"].lower()
            output.append(
                {
                    "listing_id": record["listing_id"],
                    "text_signals": {"amenities": ["pool"] if "pool" in text else []},
                    "numeric_signals": {},
                    "keywords": [],
                }
            )
        return output


class FakeSummarizer:
    def summarize(self, record, _signals):
        return f"Summary for {record['listing_id']}"


class FakeRepository:
    def __init__(self, ids):
        self.ids = set(ids)
        self.filters = []

    def find_candidate_ids(self, filters):
        self.filters.append(filters)
        return self.ids


class BrokenSearcher:
    def search_candidates(self, *_args, **_kwargs):
        raise RuntimeError("not available")


class FakeReranker:
    def rerank(self, _query, records):
        return {record["listing_id"]: 10.0 if record["listing_id"] == "2" else 1.0 for record in records}


def records():
    return [
        {
            "listing_id": "1",
            "address": "1 Main St",
            "city": "Galt",
            "price": 500000,
            "beds": 3,
            "baths": 2,
            "sqft": 1500,
            "remarks_cleaned": "Bright home with a private pool and patio.",
        },
        {
            "listing_id": "2",
            "address": "2 Main St",
            "city": "Galt",
            "price": 400000,
            "beds": 3,
            "baths": 2,
            "sqft": 1400,
            "remarks_cleaned": "Cozy home with a fireplace.",
        },
    ]


def snapshot():
    listing_records = records()
    semantic = SemanticSearcher(model=FakeEmbeddingModel()).build_index(listing_records)
    bm25 = BM25Searcher().build(listing_records)
    signals = SignalSearcher().build(
        [
            {"listing_id": "1", "text_signals": {"amenities": ["private pool"], "location_features": ["ocean view"]}},
            {"listing_id": "2", "text_signals": {"interior_features": ["fireplace"]}},
        ]
    )
    return SimpleNamespace(
        snapshot_id="test-snapshot",
        pass_listing_ids={"1", "2"},
        retrievable_listing_ids={"1", "2"},
        catalog_by_id={record["listing_id"]: record for record in listing_records},
        summaries_by_id={"1": "Pool home", "2": "Fireplace home"},
        semantic=semantic,
        bm25=bm25,
        signals=signals,
    )


def service(snapshot_data=None, repository=None, **kwargs):
    parser = QueryParser(cities=["Galt"])
    validator = SchemaValidator(cities=["Galt"])
    kwargs.setdefault("enable_cross_encoder", False)
    return SearchService(
        snapshot_data or snapshot(),
        repository or FakeRepository({"1", "2"}),
        parser=parser,
        validator=validator,
        **kwargs,
    )


def test_repository_builds_parameterized_structured_filters_only():
    repository = ListingRepository()
    sql, params = repository.build_query({"city": "Galt", "price_max": 500000, "county": "Sacramento"})

    assert "L_City = %s" in sql
    assert "L_SystemPrice <= %s" in sql
    assert "county" not in sql.lower()
    assert params == ["Galt", 500000]


def test_signal_search_respects_specific_and_generic_signal_hierarchy():
    searcher = snapshot().signals

    assert [item["listing_id"] for item in searcher.search({"amenities": ["pool"]}, {"1", "2"})] == ["1"]
    assert [item["listing_id"] for item in searcher.search({"amenities": ["private pool"]}, {"1", "2"})] == ["1"]
    assert searcher.search({"amenities": ["community pool"]}, {"1", "2"}) == []
    assert [item["listing_id"] for item in searcher.search({"location_features": ["view"]}, {"1", "2"})] == ["1"]
    assert searcher.exclusion_matches({"amenities_exclude": ["pool"]}, {"1", "2"}) == {
        "1": [{"bucket": "amenities", "value": "pool"}]
    }


def test_signal_boost_uses_match_strength_not_signal_rank():
    searcher = service()
    fused = searcher._fuse_sources(
        {
            "signals": [
                {"listing_id": "1", "rank": 1, "score": 1.0, "matches": [{"bucket": "amenities", "value": "pool"}]},
                {"listing_id": "2", "rank": 2, "score": 1.0, "matches": [{"bucket": "amenities", "value": "pool"}]},
            ]
        },
        {"amenities": ["pool"]},
        {"1": [{"bucket": "amenities", "value": "pool"}], "2": [{"bucket": "amenities", "value": "pool"}]},
        True,
    )

    assert fused["1"]["score"] == fused["2"]["score"]


def test_text_retrievers_only_return_requested_candidates():
    listing_records = records()
    semantic = SemanticSearcher(model=FakeEmbeddingModel()).build_index(listing_records)
    bm25 = BM25Searcher().build(listing_records)

    assert [item["listing_id"] for item in semantic.search_candidates("pool", {"2"})] == ["2"]
    assert [item["listing_id"] for item in bm25.search_candidates("pool", {"2"})] == ["2"]


def test_cross_encoder_document_keeps_facts_remarks_signals_and_summary_in_priority_order():
    document = CrossEncoderReranker._document(
        {
            "city": "Palm Springs",
            "price": 700000,
            "beds": 3,
            "baths": 2,
            "sqft": 1500,
            "remarks_cleaned": "Two-story home with a private pool. Fireplace is decorator only.",
            "text_signals": {"amenities": ["private pool"], "interior_features": ["fireplace"]},
            "summary": "Pool home with a fireplace.",
        }
    )

    assert "Listing facts: city: Palm Springs | price: 700000" in document
    assert "Remarks: Two-story home with a private pool. Fireplace is decorator only." in document
    assert "Features: amenities: private pool; interior_features: fireplace" in document
    assert document.endswith("Summary: Pool home with a fireplace.")
    assert len(document) <= CrossEncoderReranker.MAX_DOCUMENT_CHARS


def test_snapshot_builder_publishes_only_pass_listings(tmp_path):
    builder = SearchSnapshotBuilder(
        model_name="fake-model",
        compliance_checker=FakeComplianceChecker(),
        signal_extractor=FakeSignalExtractor(),
        summarizer=FakeSummarizer(),
        semantic_searcher=SemanticSearcher(model_name="fake-model", model=FakeEmbeddingModel()),
    )
    source = [
        {"listing_id": "1", "city": "Galt", "remarks": "Home with a pool."},
        {"listing_id": "2", "city": "Galt", "remarks": "Restricted to a group."},
    ]
    snapshot_dir = builder.build(source, tmp_path / "search_snapshots", snapshot_id="snapshot-a")

    assert [row["listing_id"] for row in read_jsonl(snapshot_dir / "catalog.jsonl")] == ["1"]
    assert SearchSnapshot.load_active(tmp_path / "search").pass_listing_ids == {"1"}

    failed_builder = SearchSnapshotBuilder(
        model_name="broken-model",
        compliance_checker=FakeComplianceChecker(),
        signal_extractor=FakeSignalExtractor(),
        summarizer=FakeSummarizer(),
        semantic_searcher=SemanticSearcher(model_name="broken-model", model=BrokenEmbeddingModel()),
    )
    with pytest.raises(RuntimeError):
        failed_builder.build(source, tmp_path / "search_snapshots", snapshot_id="snapshot-b")
    assert SearchSnapshot.load_active(tmp_path / "search").snapshot_id == "snapshot-a"


def test_active_snapshot_falls_back_to_snapshot_id_when_path_is_relocated(tmp_path):
    builder = SearchSnapshotBuilder(
        model_name="fake-model",
        compliance_checker=FakeComplianceChecker(),
        signal_extractor=FakeSignalExtractor(),
        summarizer=FakeSummarizer(),
        semantic_searcher=SemanticSearcher(model_name="fake-model", model=FakeEmbeddingModel()),
    )
    builder.build(
        [
            {
                "listing_id": "1",
                "city": "Galt",
                "remarks": "Bright home with a private pool.",
            }
        ],
        tmp_path / "search_snapshots",
        snapshot_id="snapshot-a",
    )

    pointer_path = tmp_path / "search" / "active.json"
    pointer = json.loads(pointer_path.read_text())
    pointer["snapshot_path"] = "/unavailable-host-path/snapshot-a"
    pointer_path.write_text(json.dumps(pointer))

    assert SearchSnapshot.load_active(tmp_path / "search").snapshot_id == "snapshot-a"


def test_service_fuses_sources_and_reports_signal_matches():
    result = service().search("Find 3 bedroom homes in Galt with a pool")

    assert result["ok"] is True
    assert result["results"][0]["listing_id"] == "1"
    assert result["results"][0]["source_ranks"]
    assert result["results"][0]["matched_signals"] == [{"bucket": "amenities", "value": "pool"}]
    assert result["results"][0]["signal_status"] == "selected"
    assert "signals" not in result["results"][0]["source_ranks"]
    assert result["meta"]["applied_hard_filters"] == {"city": "Galt", "beds_min": 3}


def test_bm25_only_is_available_as_an_internal_baseline():
    snapshot_data = snapshot()
    snapshot_data.semantic = BrokenSearcher()

    result = service(snapshot_data).search_experiment("Find homes in Galt with a fireplace", "bm25_only")

    assert result["ok"] is True
    assert all(set(item["source_ranks"]) == {"bm25"} for item in result["results"])
    assert result["meta"]["candidate_counts"]["bm25"] == 2
    assert result["meta"]["candidate_counts"]["rrf_union"] == 2


def test_explicit_price_sort_overrides_relevance_and_text_sort_is_a_fallback():
    searcher = service()

    explicit = searcher.search("Find homes in Galt with a pool", sort_by="price_asc")
    inferred = searcher.search("Show me the cheapest homes in Galt")

    assert explicit["meta"]["effective_sort"] == "price_asc"
    assert explicit["meta"]["price_sort_mode"] == "soft_preference_tiers"
    assert explicit["results"][0]["listing_id"] == "1"
    assert explicit["results"][0]["match_tier"] == "signal_complete"
    assert "score" not in explicit["results"][0]
    assert inferred["meta"]["effective_sort"] == "price_asc"
    assert inferred["meta"]["price_sort_mode"] == "pure_field"
    assert inferred["results"][0]["listing_id"] == "2"
    assert "score" not in inferred["results"][0]


def test_pure_price_sort_skips_all_retrieval_components():
    class UnexpectedRetriever:
        def __getattr__(self, _name):
            raise AssertionError("pure price sorting should not retrieve text candidates")

    snapshot_data = snapshot()
    snapshot_data.semantic = UnexpectedRetriever()
    snapshot_data.bm25 = UnexpectedRetriever()
    snapshot_data.signals = UnexpectedRetriever()

    result = service(snapshot_data).search("Show me the cheapest homes in Galt", top_k=2)

    assert [item["listing_id"] for item in result["results"]] == ["2", "1"]
    assert all(item["match_tier"] == "field_price" for item in result["results"])
    assert all("score" not in item for item in result["results"])


def test_multi_signal_price_sort_prioritizes_complete_then_partial_matches():
    snapshot_data = snapshot()
    complete_match = {
        "listing_id": "3",
        "address": "3 Main St",
        "city": "Galt",
        "price": 600000,
        "beds": 3,
        "baths": 2,
        "sqft": 1600,
        "remarks_cleaned": "",
    }
    snapshot_data.catalog_by_id["3"] = complete_match
    snapshot_data.summaries_by_id["3"] = "Pool and fireplace home"
    snapshot_data.pass_listing_ids.add("3")
    snapshot_data.signals = SignalSearcher().build(
        [
            {"listing_id": "1", "text_signals": {"amenities": ["private pool"]}},
            {"listing_id": "2", "text_signals": {"interior_features": ["fireplace"]}},
            {
                "listing_id": "3",
                "text_signals": {"amenities": ["private pool"], "interior_features": ["fireplace"]},
            },
        ]
    )

    result = service(snapshot_data, FakeRepository({"1", "2", "3"})).search(
        "Find homes in Galt with a pool and fireplace",
        top_k=3,
        sort_by="price_asc",
    )

    assert [item["listing_id"] for item in result["results"]] == ["3", "2", "1"]
    assert [item["match_tier"] for item in result["results"]] == [
        "signal_complete",
        "signal_partial",
        "signal_partial",
    ]


def test_partial_signal_tier_uses_match_strength_before_price():
    searcher = service()
    ordered = searcher._sorted_signal_matches(
        {
            "1": {"score": 1.0},
            "2": {"score": 2.0},
        },
        "price_asc",
        use_match_strength=True,
    )

    assert ordered == ["2", "1"]


def test_soft_price_sort_uses_text_fallback_only_after_signal_tier():
    result = service().search("Find homes in Galt with a pool", top_k=2, sort_by="price_asc")

    assert result["results"][0]["match_tier"] == "signal_complete"
    assert result["results"][1]["match_tier"] == "semantic_lexical_fallback"
    assert result["meta"]["fallback_candidate_count"] == 2


def test_default_search_uses_cross_encoder_with_a_50_listing_window():
    searcher = SearchService(
        snapshot(),
        FakeRepository({"1", "2"}),
        parser=QueryParser(cities=["Galt"]),
        validator=SchemaValidator(cities=["Galt"]),
        reranker=FakeReranker(),
    )
    result = searcher.search("Find homes in Galt")

    assert searcher.enable_cross_encoder is True
    assert searcher.rerank_k == 50
    assert result["meta"]["variant"] == "hybrid_cross_encoder"
    assert result["meta"]["requested_profile"] == "quality"
    assert result["meta"]["effective_profile"] == "quality"
    assert result["meta"]["reranker_used"] is True
    assert "cross_encoder_rerank" in result["meta"]["timings_ms"]
    assert result["results"][0]["listing_id"] == "2"
    assert result["results"][0]["pre_rerank_rank"]
    assert result["results"][0]["post_rerank_rank"] == 1
    assert result["results"][0]["cross_encoder_score"] == 10.0
    assert "retrieval_evidence" in result["results"][0]


def test_fast_profile_uses_hybrid_rrf_without_cross_encoder():
    result = service().search("Find homes in Galt with a pool", search_profile="fast")

    assert result["meta"]["variant"] == "dense_bm25_signal_rrf"
    assert result["meta"]["requested_profile"] == "fast"
    assert result["meta"]["effective_profile"] == "fast"
    assert result["meta"]["reranker_used"] is False
    assert "cross_encoder_rerank" not in result["meta"]["timings_ms"]


def test_price_sort_does_not_apply_a_relevance_profile():
    result = service().search(
        "Find homes in Galt with a pool",
        sort_by="price_asc",
        search_profile="quality",
    )

    assert result["meta"]["requested_profile"] == "quality"
    assert result["meta"]["effective_profile"] == "structured_price_sort"
    assert result["meta"]["reranker_used"] is False


def test_search_rejects_unknown_profile():
    with pytest.raises(ValueError, match="Unsupported search profile"):
        service().search("Find homes in Galt", search_profile="experimental")


def test_parallel_retrieval_matches_serial_results():
    query = "Find homes in Galt with a pool"
    serial = service(parallel_retrieval=False).search(query, top_k=2)
    parallel = service(parallel_retrieval=True).search(query, top_k=2)

    assert parallel["parsed_query"] == serial["parsed_query"]
    assert parallel["results"] == serial["results"]
    assert parallel["meta"]["candidate_counts"] == serial["meta"]["candidate_counts"]
    assert parallel["meta"]["signal_selection"] == serial["meta"]["signal_selection"]
    assert parallel["meta"]["degraded_components"] == serial["meta"]["degraded_components"]
    assert serial["meta"]["retrieval_execution"] == "serial"
    assert parallel["meta"]["retrieval_execution"] == "parallel"
    assert "retrieval_wall" in parallel["meta"]["timings_ms"]


def test_parallel_retrieval_runs_independent_sources_concurrently():
    snapshot_data = snapshot()
    barrier = threading.Barrier(3)
    task_threads = {}

    def mark_task(name):
        task_threads[name] = threading.get_ident()
        barrier.wait(timeout=2)

    original_encode = snapshot_data.semantic.encode_query
    original_bm25 = snapshot_data.bm25.search_candidates
    original_match = snapshot_data.signals.match

    def encode_query(query):
        mark_task("dense")
        return original_encode(query)

    def search_candidates(query, candidate_ids, top_k):
        mark_task("bm25")
        return original_bm25(query, candidate_ids, top_k)

    def match(soft_signals, candidate_ids):
        mark_task("signals")
        return original_match(soft_signals, candidate_ids)

    snapshot_data.semantic.encode_query = encode_query
    snapshot_data.bm25.search_candidates = search_candidates
    snapshot_data.signals.match = match

    result = service(snapshot_data, parallel_retrieval=True, retrieval_workers=3).search(
        "Find homes in Galt with a pool"
    )

    assert result["ok"] is True
    assert result["meta"]["retrieval_execution"] == "parallel"
    assert set(task_threads) == {"dense", "bm25", "signals"}
    assert len(set(task_threads.values())) == 3


def test_retrieval_workers_must_be_positive():
    with pytest.raises(ValueError, match="retrieval_workers"):
        service(retrieval_workers=0)


def test_cross_encoder_trace_keeps_signal_only_candidates_explainable():
    snapshot_data = snapshot()
    snapshot_data.catalog_by_id["3"] = {
        "listing_id": "3",
        "address": "3 Main St",
        "city": "Galt",
        "price": 450000,
        "beds": 3,
        "baths": 2,
        "sqft": 1450,
        "remarks_cleaned": "",
    }
    snapshot_data.summaries_by_id["3"] = "Pool home"
    snapshot_data.pass_listing_ids.add("3")
    snapshot_data.signals = SignalSearcher().build(
        [
            {"listing_id": "1", "text_signals": {"amenities": ["private pool"]}},
            {"listing_id": "2", "text_signals": {"interior_features": ["fireplace"]}},
            {"listing_id": "3", "text_signals": {"amenities": ["pool"]}},
        ]
    )

    result = service(
        snapshot_data,
        FakeRepository({"1", "2", "3"}),
        enable_cross_encoder=True,
        reranker=FakeReranker(),
    ).search_experiment("Find homes in Galt with a pool", "hybrid_cross_encoder", top_k=3)

    signal_only = next(item for item in result["results"] if item["listing_id"] == "3")
    assert signal_only["source_ranks"] == {}
    assert signal_only["matched_signals"] == [{"bucket": "amenities", "value": "pool"}]
    assert signal_only["retrieval_evidence"] == "signal: pool"
    assert signal_only["cross_encoder_score"] == 1.0
    assert signal_only["pre_rerank_rank"]


def test_dense_failure_degrades_to_other_sources():
    snapshot_data = snapshot()
    snapshot_data.semantic = BrokenSearcher()

    result = service(snapshot_data, parallel_retrieval=True).search("Find homes in Galt with a pool")

    assert result["ok"] is True
    assert "dense" in result["meta"]["degraded_components"]
    assert result["results"][0]["listing_id"] == "1"


def test_structured_fallback_only_fills_generic_search_results():
    snapshot_data = snapshot()
    textless = {
        "listing_id": "3",
        "address": "3 Main St",
        "city": "Galt",
        "price": 450000,
        "beds": 3,
        "baths": 2,
        "sqft": 1450,
        "remarks_cleaned": "",
    }
    snapshot_data.catalog_by_id["3"] = textless
    snapshot_data.pass_listing_ids.add("3")

    generic = service(snapshot_data, FakeRepository({"1", "2", "3"})).search(
        "Find 3 bedroom homes in Galt",
        top_k=3,
    )
    pool = service(snapshot_data, FakeRepository({"1", "2", "3"})).search(
        "Find 3 bedroom homes in Galt with a pool",
        top_k=3,
    )

    fallback = next(item for item in generic["results"] if item["listing_id"] == "3")
    assert fallback["retrieval_status"] == "structured_fallback"
    assert fallback["score"] == 0.0
    assert all(item["listing_id"] != "3" for item in pool["results"])


def test_warm_up_is_reported_separately_from_search_latency():
    result = service().warm_up()

    assert result["timings_ms"]["dense_warm_up"] >= 0


def test_structured_filter_failure_fails_closed():
    class BrokenRepository:
        def find_candidate_ids(self, _filters):
            raise RuntimeError("database unavailable")

    with pytest.raises(SearchUnavailableError):
        service(repository=BrokenRepository()).search("Find homes in Galt")
