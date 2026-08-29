from types import SimpleNamespace

import numpy as np
import pytest

from src.real_estate_nlp.keyword_search import BM25Searcher
from src.real_estate_nlp.listing_repository import ListingRepository
from src.real_estate_nlp.query_parser import QueryParser
from src.real_estate_nlp.schema_validator import SchemaValidator
from src.real_estate_nlp.search_service import SearchService, SearchUnavailableError
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
        catalog_by_id={record["listing_id"]: record for record in listing_records},
        summaries_by_id={"1": "Pool home", "2": "Fireplace home"},
        semantic=semantic,
        bm25=bm25,
        signals=signals,
    )


def service(snapshot_data=None, repository=None, **kwargs):
    parser = QueryParser(cities=["Galt"])
    validator = SchemaValidator(cities=["Galt"])
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


def test_text_retrievers_only_return_requested_candidates():
    listing_records = records()
    semantic = SemanticSearcher(model=FakeEmbeddingModel()).build_index(listing_records)
    bm25 = BM25Searcher().build(listing_records)

    assert [item["listing_id"] for item in semantic.search_candidates("pool", {"2"})] == ["2"]
    assert [item["listing_id"] for item in bm25.search_candidates("pool", {"2"})] == ["2"]


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


def test_service_fuses_sources_and_reports_signal_matches():
    result = service().search("Find 3 bedroom homes in Galt with a pool")

    assert result["ok"] is True
    assert result["results"][0]["listing_id"] == "1"
    assert result["results"][0]["source_ranks"]
    assert result["results"][0]["matched_signals"] == [{"bucket": "amenities", "value": "pool"}]
    assert result["meta"]["applied_hard_filters"] == {"city": "Galt", "beds_min": 3}


def test_explicit_price_sort_overrides_relevance_and_text_sort_is_a_fallback():
    searcher = service()

    explicit = searcher.search("Find homes in Galt with a pool", sort_by="price_asc")
    inferred = searcher.search("Show me the cheapest homes in Galt")

    assert explicit["meta"]["effective_sort"] == "price_asc"
    assert explicit["results"][0]["listing_id"] == "2"
    assert inferred["meta"]["effective_sort"] == "price_asc"


def test_cross_encoder_is_experimental_and_disabled_by_default():
    default = service().search("Find homes in Galt")
    experimental = service(enable_cross_encoder=True, reranker=FakeReranker()).search_experiment(
        "Find homes in Galt", "hybrid_cross_encoder"
    )

    assert "cross_encoder" not in default["meta"]["timings_ms"]
    assert experimental["results"][0]["listing_id"] == "2"


def test_dense_failure_degrades_to_other_sources():
    snapshot_data = snapshot()
    snapshot_data.semantic = BrokenSearcher()

    result = service(snapshot_data).search("Find homes in Galt with a pool")

    assert result["ok"] is True
    assert "dense" in result["meta"]["degraded_components"]
    assert result["results"][0]["listing_id"] == "1"


def test_structured_filter_failure_fails_closed():
    class BrokenRepository:
        def find_candidate_ids(self, _filters):
            raise RuntimeError("database unavailable")

    with pytest.raises(SearchUnavailableError):
        service(repository=BrokenRepository()).search("Find homes in Galt")
