"""Aggregation helpers for local product-web analytics."""

from __future__ import annotations

import math
from collections import Counter


PROFILE_NAMES = ("fast", "balanced", "quality")


def summarize_web_events(events):
    """Return privacy-preserving search and feedback metrics from web events."""
    searches = [event for event in events if event.get("event_type") == "search"]
    feedback = [event for event in events if event.get("event_type") == "feedback"]
    helpful = [event for event in feedback if event.get("feedback") == "helpful"]

    profile_usage = Counter(
        event["search_profile"]
        for event in searches
        if event.get("search_profile") in PROFILE_NAMES
    )
    result_counts = [event.get("result_count", 0) for event in searches]

    return {
        "query_volume": len(searches),
        "unique_sessions": len({event.get("session_id") for event in searches if event.get("session_id")}),
        "comparison_searches": sum(bool(event.get("comparison_enabled")) for event in searches),
        "profile_usage": {profile: profile_usage.get(profile, 0) for profile in PROFILE_NAMES},
        "latency_ms": {
            "client": _latency_summary(event.get("client_latency_ms") for event in searches),
            "api": _latency_summary(event.get("api_latency_ms") for event in searches),
        },
        "profile_latency_ms": {
            profile: {
                "client": _latency_summary(
                    event.get("client_latency_ms")
                    for event in searches
                    if event.get("search_profile") == profile
                ),
                "api": _latency_summary(
                    event.get("api_latency_ms")
                    for event in searches
                    if event.get("search_profile") == profile
                ),
            }
            for profile in PROFILE_NAMES
        },
        "zero_result_rate": _ratio(sum(count == 0 for count in result_counts), len(result_counts)),
        "satisfaction": {
            "responses": len(feedback),
            "helpful": len(helpful),
            "helpful_rate": _ratio(len(helpful), len(feedback)),
        },
    }


def _latency_summary(values):
    values = sorted(float(value) for value in values if value is not None)
    return {
        "count": len(values),
        "p50": _percentile(values, 0.5),
        "p90": _percentile(values, 0.9),
        "p95": _percentile(values, 0.95),
    }


def _percentile(values, quantile):
    if not values:
        return None
    index = (len(values) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return round(values[lower], 2)
    return round(values[lower] + (values[upper] - values[lower]) * (index - lower), 2)


def _ratio(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator, 4)
