from src.real_estate_nlp.api.web_metrics import summarize_web_events


def test_web_metrics_summarize_searches_feedback_and_latency():
    metrics = summarize_web_events(
        [
            {
                "event_type": "search",
                "session_id": "one",
                "search_profile": "fast",
                "client_latency_ms": 50,
                "api_latency_ms": 40,
                "result_count": 0,
            },
            {
                "event_type": "search",
                "session_id": "two",
                "search_profile": "quality",
                "comparison_enabled": True,
                "client_latency_ms": 150,
                "api_latency_ms": 120,
                "result_count": 5,
            },
            {"event_type": "feedback", "session_id": "two", "feedback": "helpful"},
            {"event_type": "feedback", "session_id": "one", "feedback": "not_helpful"},
        ]
    )

    assert metrics["query_volume"] == 2
    assert metrics["unique_sessions"] == 2
    assert metrics["comparison_searches"] == 1
    assert metrics["profile_usage"] == {"fast": 1, "balanced": 0, "quality": 1}
    assert metrics["latency_ms"]["client"] == {
        "count": 2,
        "p50": 100.0,
        "p90": 140.0,
        "p95": 145.0,
    }
    assert metrics["profile_latency_ms"]["fast"]["api"] == {
        "count": 1,
        "p50": 40.0,
        "p90": 40.0,
        "p95": 40.0,
    }
    assert metrics["zero_result_rate"] == 0.5
    assert metrics["satisfaction"] == {"responses": 2, "helpful": 1, "helpful_rate": 0.5}


def test_web_metrics_handles_empty_event_history():
    metrics = summarize_web_events([])

    assert metrics["query_volume"] == 0
    assert metrics["latency_ms"]["api"] == {
        "count": 0,
        "p50": None,
        "p90": None,
        "p95": None,
    }
    assert metrics["zero_result_rate"] is None
    assert metrics["satisfaction"]["helpful_rate"] is None
