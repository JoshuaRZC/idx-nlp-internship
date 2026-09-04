"""Public FastAPI application for real estate NLP capabilities."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from src.real_estate_nlp.api.config import ApiSettings
from src.real_estate_nlp.api.container import ApiContainer
from src.real_estate_nlp.api.schemas import (
    ComplianceResponse,
    EntityResponse,
    HealthResponse,
    IntentResponse,
    ParseQueryResponse,
    ReadyResponse,
    SearchRequest,
    SearchResponse,
    SummaryResponse,
    SummarizeRequest,
    TextRequest,
)
from src.real_estate_nlp.search_service import SearchUnavailableError


LOGGER = logging.getLogger(__name__)
RATE_LIMITED_PATHS = {
    "/search",
    "/parse-query",
    "/extract-entities",
    "/summarize",
    "/check-compliance",
    "/classify-intent",
}


def create_app(settings: ApiSettings | None = None, container: ApiContainer | None = None):
    """Build an app with injectable dependencies for tests and local use."""
    settings = settings or ApiSettings.from_env()
    container = container or ApiContainer(settings=settings)

    @asynccontextmanager
    async def lifespan(app):
        await run_in_threadpool(container.start)
        yield
        await run_in_threadpool(container.stop)

    app = FastAPI(
        title="Real Estate NLP API",
        version="1.0.0",
        description="Search and listing-text NLP services.",
        lifespan=lifespan,
    )
    app.state.container = container

    @app.middleware("http")
    async def request_context_and_rate_limit(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()

        if request.method == "POST" and request.url.path in RATE_LIMITED_PATHS and container.ready:
            client_ip = request.client.host if request.client else "unknown"
            try:
                allowed, retry_after_ms = await run_in_threadpool(
                    container.store.allow_request,
                    client_ip,
                    settings.rate_limit_requests,
                    settings.rate_limit_window_seconds,
                )
            except Exception:
                LOGGER.exception("Rate limit check failed request_id=%s", request_id)
                response = _error_response(503, "rate_limit_unavailable", "Rate limiting is unavailable.")
                response.headers["X-Request-ID"] = request_id
                return response
            if not allowed:
                response = _error_response(429, "rate_limited", "Rate limit exceeded.")
                response.headers["Retry-After"] = str(max(1, (retry_after_ms + 999) // 1000))
                response.headers["X-Request-ID"] = request_id
                return response

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        LOGGER.info(
            "api_request method=%s path=%s status=%s latency_ms=%.2f cache=%s snapshot=%s degraded=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started_at) * 1000,
            response.headers.get("X-Cache", "BYPASS"),
            container.snapshot_id or "none",
            response.headers.get("X-Search-Degraded", "none"),
            request_id,
        )
        return response

    @app.exception_handler(SearchUnavailableError)
    async def search_unavailable_handler(request, _error):
        return _error_response(503, "search_unavailable", "Search is temporarily unavailable.")

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request, _error):
        LOGGER.exception("Unhandled API error request_id=%s", getattr(request.state, "request_id", "unknown"))
        return _error_response(500, "internal_error", "An unexpected server error occurred.")

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    async def health_check():
        return {"status": "ok"}

    @app.get("/ready", response_model=ReadyResponse, tags=["operations"])
    async def readiness_check():
        if not container.ready:
            raise HTTPException(status_code=503, detail="API dependencies are not ready.")
        return {"status": "ready", "snapshot_id": container.snapshot_id}

    @app.post("/search", response_model=SearchResponse, tags=["search"])
    async def search_listings(body: SearchRequest, response: Response):
        _require_ready(container)
        payload = body.dict()
        cache_version = container.snapshot_id or "unknown-snapshot"
        return await _cached(
            container,
            response,
            "search",
            payload,
            settings.search_cache_ttl_seconds,
            cache_version,
            lambda: _search_response(container.search_service.search(**payload), body.query),
        )

    @app.post("/parse-query", response_model=ParseQueryResponse, tags=["nlp"])
    async def parse_query(body: TextRequest, response: Response):
        _require_ready(container)
        return await _cached(
            container,
            response,
            "parse-query",
            body.dict(),
            settings.default_cache_ttl_seconds,
            "parser-v1",
            lambda: {"parsed_query": container.search_service.parser.parse(body.text)},
        )

    @app.post("/extract-entities", response_model=EntityResponse, tags=["nlp"])
    async def extract_entities(body: TextRequest, response: Response):
        _require_ready(container)
        return await _cached(
            container,
            response,
            "extract-entities",
            body.dict(),
            settings.default_cache_ttl_seconds,
            "entity-rules-v1",
            lambda: {"entities": container.entity_extractor.extract_all(body.text)},
        )

    @app.post("/summarize", response_model=SummaryResponse, tags=["nlp"])
    async def summarize_listing(body: SummarizeRequest, response: Response):
        _require_ready(container)
        payload = body.dict(exclude_none=True)
        return await _cached(
            container,
            response,
            "summarize",
            payload,
            settings.default_cache_ttl_seconds,
            "summarizer-v1",
            lambda: {
                "summary": container.summarizer.summarize(
                    payload["listing"],
                    payload.get("signals"),
                    num_sentences=body.num_sentences,
                )
            },
        )

    @app.post("/check-compliance", response_model=ComplianceResponse, tags=["nlp"])
    async def check_compliance(body: TextRequest, response: Response):
        _require_ready(container)
        rule_version = container.compliance_checker.rule_version
        return await _cached(
            container,
            response,
            "check-compliance",
            body.dict(),
            settings.default_cache_ttl_seconds,
            f"compliance-{rule_version}",
            lambda: container.compliance_checker.check_listing(body.text),
        )

    @app.post("/classify-intent", response_model=IntentResponse, tags=["nlp"])
    async def classify_intent(body: TextRequest, response: Response):
        _require_ready(container)
        return await _cached(
            container,
            response,
            "classify-intent",
            body.dict(),
            settings.default_cache_ttl_seconds,
            "intent-v1",
            lambda: container.intent_classifier.predict(body.text),
        )

    return app


async def _cached(
    container: ApiContainer,
    response: Response,
    endpoint: str,
    payload: dict[str, Any],
    ttl_seconds: int,
    version: str,
    operation: Callable[[], dict[str, Any]],
):
    key = container.store.cache_key(endpoint, payload, version=version)
    cached = await run_in_threadpool(container.store.get_json, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        _set_search_headers(response, endpoint, cached)
        return cached

    value = await run_in_threadpool(operation)
    await run_in_threadpool(container.store.set_json, key, value, ttl_seconds)
    response.headers["X-Cache"] = "MISS"
    _set_search_headers(response, endpoint, value)
    return value


def _search_response(result, query):
    meta = result.get("meta", {})
    public_meta = {
        "snapshot_id": meta.get("snapshot_id", "unknown"),
        "requested_profile": meta.get("requested_profile", "quality"),
        "effective_profile": meta.get("effective_profile", "quality"),
        "reranker_used": meta.get("reranker_used", False),
        "effective_sort": meta.get("effective_sort"),
        "eligible_count": meta.get("eligible_count"),
        "degraded_components": meta.get("degraded_components", []),
        "timings_ms": meta.get("timings_ms", {}),
    }
    fields = {
        "listing_id",
        "address",
        "city",
        "price",
        "beds",
        "baths",
        "sqft",
        "summary",
        "rank",
        "matched_signals",
        "excluded_signals",
        "signal_status",
        "retrieval_status",
        "retrieval_evidence",
    }
    results = [{key: item.get(key) for key in fields} for item in result.get("results", [])]
    return {
        "ok": result["ok"],
        "message": result["message"],
        "query": query,
        "parsed_query": result.get("parsed_query", {}),
        "results": results,
        "meta": public_meta,
    }


def _require_ready(container):
    if not container.ready:
        raise HTTPException(status_code=503, detail="API dependencies are not ready.")


def _set_search_headers(response, endpoint, value):
    if endpoint != "search":
        return
    components = value.get("meta", {}).get("degraded_components", [])
    response.headers["X-Search-Degraded"] = ",".join(components) or "none"


def _error_response(status_code, code, message):
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


app = create_app()
