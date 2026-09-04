"""Pydantic request and response models for the public API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, confloat, conint, validator


NonNegativeNumber = conint(strict=True, ge=0) | confloat(strict=True, ge=0)
CountNumber = conint(strict=True, ge=0, le=100) | confloat(strict=True, ge=0, le=100)


class ApiModel(BaseModel):
    class Config:
        extra = "forbid"


class TextRequest(ApiModel):
    text: str = Field(..., min_length=1, max_length=20_000)

    @validator("text")
    def strip_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class SearchRequest(ApiModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(10, ge=1, le=50)
    sort_by: Literal["relevance", "price_asc", "price_desc"] | None = None
    search_profile: Literal["fast", "quality"] = "quality"

    @validator("query")
    def strip_query(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value


class SignalInput(ApiModel):
    text_signals: dict[str, list[str]] = Field(default_factory=dict)


class ListingInput(ApiModel):
    listing_id: str | None = Field(None, max_length=100)
    address: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=100)
    price: NonNegativeNumber | None = None
    beds: CountNumber | None = None
    baths: CountNumber | None = None
    sqft: conint(strict=True, ge=0, le=1_000_000) | None = None
    remarks: str | None = Field(None, max_length=20_000)


class SummarizeRequest(ApiModel):
    listing: ListingInput
    signals: SignalInput | None = None
    num_sentences: int = Field(2, ge=1, le=3)


class EntityResponse(ApiModel):
    entities: list[dict[str, Any]]


class SummaryResponse(ApiModel):
    summary: str


class ComplianceResponse(ApiModel):
    status: Literal["pass", "review", "blocked"]
    can_publish: bool
    rule_version: str
    findings: list[dict[str, Any]]


class IntentResponse(ApiModel):
    label: Literal["browsing", "researching", "high_intent_inquiry"]
    confidence: float = Field(..., ge=0, le=1)
    is_uncertain: bool


class ParseQueryResponse(ApiModel):
    parsed_query: dict[str, Any]


class SearchResult(ApiModel):
    listing_id: str
    address: str | None = None
    city: str | None = None
    price: NonNegativeNumber | None = None
    beds: CountNumber | None = None
    baths: CountNumber | None = None
    sqft: NonNegativeNumber | None = None
    summary: str = ""
    rank: int
    matched_signals: list[dict[str, Any]] = Field(default_factory=list)
    excluded_signals: list[dict[str, Any]] = Field(default_factory=list)
    signal_status: str
    retrieval_status: str
    retrieval_evidence: str = ""


class SearchMeta(ApiModel):
    snapshot_id: str
    requested_profile: Literal["fast", "quality"]
    effective_profile: Literal["fast", "quality", "structured_price_sort", "not_run"]
    reranker_used: bool
    effective_sort: str | None = None
    eligible_count: int | None = None
    degraded_components: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)


class SearchResponse(ApiModel):
    ok: bool
    message: str
    query: str
    parsed_query: dict[str, Any]
    results: list[SearchResult]
    meta: SearchMeta


class HealthResponse(ApiModel):
    status: str


class ReadyResponse(ApiModel):
    status: str
    snapshot_id: str | None = None
