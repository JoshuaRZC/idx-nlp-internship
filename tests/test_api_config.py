from src.real_estate_nlp.api.config import ApiSettings


def test_api_settings_read_rerank_tuning_and_web_metrics_environment(monkeypatch):
    monkeypatch.setenv("API_RERANK_K", "30")
    monkeypatch.setenv("API_RERANK_MAX_REMARK_CHARS", "900")
    monkeypatch.setenv("API_WEB_METRICS_TOKEN", "web-token")
    monkeypatch.setenv("API_WEB_METRICS_MAX_EVENTS", "500")
    monkeypatch.setenv("API_WEB_METRICS_TTL_SECONDS", "3600")

    settings = ApiSettings.from_env()

    assert settings.rerank_k == 30
    assert settings.rerank_max_remark_chars == 900
    assert settings.web_metrics_token == "web-token"
    assert settings.web_metrics_max_events == 500
    assert settings.web_metrics_ttl_seconds == 3600
