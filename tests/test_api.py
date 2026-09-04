from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.real_estate_nlp.api.app import create_app
from src.real_estate_nlp.api.config import ApiSettings
from src.real_estate_nlp.api.container import ApiContainer
from src.real_estate_nlp.search_service import SearchUnavailableError


class FakeStore:
    def __init__(self, allowed=True, fail_ping=False):
        self.allowed = allowed
        self.fail_ping = fail_ping
        self.values = {}
        self.closed = False

    def ping(self):
        if self.fail_ping:
            raise RuntimeError("redis unavailable")
        return True

    def close(self):
        self.closed = True

    def cache_key(self, endpoint, payload, version="default"):
        return f"{endpoint}:{version}:{sorted(payload.items())}"

    def get_json(self, key):
        return self.values.get(key)

    def set_json(self, key, value, _ttl_seconds):
        self.values[key] = value

    def allow_request(self, _client_ip, _limit, _window_seconds):
        return self.allowed, 500


class FakeParser:
    def parse(self, text):
        return {
            "intent": "search",
            "filters": {"city": "Irvine"},
            "hard_filters": {"city": "Irvine"},
            "soft_signals": {},
            "language_intent": {"label": "browsing", "confidence": 0.8, "is_uncertain": False},
        }


class FakeSearchService:
    def __init__(self, unavailable=False):
        self.snapshot = SimpleNamespace(snapshot_id="snapshot-test")
        self.parser = FakeParser()
        self.unavailable = unavailable
        self.calls = 0
        self.profiles = []
        self.warmed = False

    def warm_up(self, include_cross_encoder=False):
        self.warmed = include_cross_encoder
        return {"timings_ms": {}}

    def search(self, query, top_k=10, sort_by=None, search_profile="quality"):
        self.calls += 1
        self.profiles.append(search_profile)
        if self.unavailable:
            raise SearchUnavailableError("snapshot unavailable")
        return {
            "ok": True,
            "message": "Results found.",
            "parsed_query": self.parser.parse(query),
            "results": [
                {
                    "listing_id": "A1",
                    "address": "1 Main St",
                    "city": "Irvine",
                    "price": 950000,
                    "beds": 3,
                    "baths": 2.5,
                    "sqft": 1800,
                    "summary": "A pool home.",
                    "rank": 1,
                    "matched_signals": [{"bucket": "amenities", "value": "pool"}],
                    "excluded_signals": [],
                    "signal_status": "selected",
                    "retrieval_status": "text_retrieval",
                    "retrieval_evidence": "dense #1",
                    "remarks_cleaned": "Private MLS remarks must not be returned.",
                    "cross_encoder_score": 8.2,
                }
            ][:top_k],
            "meta": {
                "snapshot_id": "snapshot-test",
                "requested_profile": search_profile,
                "effective_profile": "structured_price_sort" if sort_by else search_profile,
                "reranker_used": search_profile == "quality" and sort_by is None,
                "effective_sort": sort_by or "relevance",
                "eligible_count": 1,
                "degraded_components": [],
                "timings_ms": {"total": 12.5},
                "candidate_counts": {"rrf_union": 1},
            },
        }


class FakeExtractor:
    def extract_all(self, text):
        return [{"label": "amenity", "value": "pool", "text": text, "start": 0, "end": 4}]


class FakeSummarizer:
    def summarize(self, record, signals=None, num_sentences=2):
        return f"{record.get('city')} summary with {num_sentences} sentences."


class FakeComplianceChecker:
    rule_version = "rules-test"

    def check_listing(self, text):
        return {
            "status": "blocked" if "children" in text.lower() else "pass",
            "can_publish": "children" not in text.lower(),
            "rule_version": self.rule_version,
            "findings": [],
        }


class FakeIntentClassifier:
    def predict(self, _text):
        return {"label": "browsing", "confidence": 0.8, "is_uncertain": False}


def make_client(store=None, search_service=None):
    settings = ApiSettings(redis_url="redis://test")
    container = ApiContainer(
        settings=settings,
        search_service=search_service or FakeSearchService(),
        entity_extractor=FakeExtractor(),
        summarizer=FakeSummarizer(),
        compliance_checker=FakeComplianceChecker(),
        intent_classifier=FakeIntentClassifier(),
        store=store or FakeStore(),
    )
    return TestClient(create_app(settings=settings, container=container)), container


def test_api_exposes_all_nlp_capabilities_and_readiness():
    client, container = make_client()
    with client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json() == {"status": "ready", "snapshot_id": "snapshot-test"}
        paths = client.get("/openapi.json").json()["paths"]
        assert {
            "/search",
            "/parse-query",
            "/extract-entities",
            "/summarize",
            "/check-compliance",
            "/classify-intent",
            "/health",
            "/ready",
        } <= set(paths)

        assert client.post("/parse-query", json={"text": "homes in Irvine"}).status_code == 200
        assert client.post("/extract-entities", json={"text": "pool"}).json()["entities"][0]["value"] == "pool"
        assert client.post(
            "/summarize",
            json={"listing": {"city": "Irvine", "remarks": "Pool home."}},
        ).json()["summary"] == "Irvine summary with 2 sentences."
        assert client.post("/check-compliance", json={"text": "No children permitted."}).json()["status"] == "blocked"
        assert client.post("/classify-intent", json={"text": "show homes"}).json()["label"] == "browsing"

    assert container.search_service.warmed is True
    assert container.store.closed is True


def test_search_uses_public_result_fields_and_caches_successful_response():
    client, container = make_client()
    with client:
        first = client.post("/search", json={"query": "homes in Irvine", "top_k": 1})
        second = client.post("/search", json={"query": "homes in Irvine", "top_k": 1})
        container.search_service.snapshot.snapshot_id = "snapshot-next"
        third = client.post("/search", json={"query": "homes in Irvine", "top_k": 1})
        fast = client.post(
            "/search",
            json={"query": "homes in Irvine", "top_k": 1, "search_profile": "fast"},
        )

    result = first.json()["results"][0]
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert third.headers["X-Cache"] == "MISS"
    assert fast.headers["X-Cache"] == "MISS"
    assert container.search_service.calls == 3
    assert container.search_service.profiles == ["quality", "quality", "fast"]
    assert "remarks_cleaned" not in result
    assert "cross_encoder_score" not in result
    assert result["summary"] == "A pool home."
    assert result["baths"] == 2.5
    assert first.json()["meta"]["effective_profile"] == "quality"
    assert first.json()["meta"]["reranker_used"] is True
    assert fast.json()["meta"]["effective_profile"] == "fast"
    assert fast.json()["meta"]["reranker_used"] is False
    assert first.headers["X-Request-ID"]


def test_api_rejects_blank_or_invalid_requests():
    client, _ = make_client()
    with client:
        assert client.post("/search", json={"query": "   "}).status_code == 422
        assert client.post("/search", json={"query": "homes", "top_k": 51}).status_code == 422
        assert client.post("/extract-entities", json={"text": ""}).status_code == 422
        assert client.post("/summarize", json={"listing": {"city": "Irvine", "unknown": "value"}}).status_code == 422


def test_rate_limit_returns_retry_after_header():
    client, _ = make_client(store=FakeStore(allowed=False))
    with client:
        response = client.post("/parse-query", json={"text": "homes in Irvine"})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert response.headers["Retry-After"] == "1"


def test_unready_process_keeps_liveness_but_blocks_nlp_endpoints():
    client, _ = make_client(store=FakeStore(fail_ping=True))
    with client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.post("/search", json={"query": "homes in Irvine"}).status_code == 503


def test_warm_up_failure_keeps_process_unready():
    class BrokenWarmUpSearch(FakeSearchService):
        def warm_up(self, include_cross_encoder=False):
            raise RuntimeError("model unavailable")

    client, _ = make_client(search_service=BrokenWarmUpSearch())
    with client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503


def test_search_dependency_failure_returns_503():
    client, _ = make_client(search_service=FakeSearchService(unavailable=True))
    with client:
        response = client.post("/search", json={"query": "homes in Irvine"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "search_unavailable"
