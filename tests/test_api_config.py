from src.real_estate_nlp.api.config import ApiSettings


def test_api_settings_read_rerank_tuning_environment(monkeypatch):
    monkeypatch.setenv("API_RERANK_K", "30")
    monkeypatch.setenv("API_RERANK_MAX_REMARK_CHARS", "900")

    settings = ApiSettings.from_env()

    assert settings.rerank_k == 30
    assert settings.rerank_max_remark_chars == 900
