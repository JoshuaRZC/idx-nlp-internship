from web.config import WebSettings


def test_web_settings_reads_admin_mode_from_environment(monkeypatch):
    monkeypatch.setenv("WEB_ADMIN_MODE", "true")

    assert WebSettings.from_env().admin_mode is True


def test_web_settings_keeps_admin_mode_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WEB_ADMIN_MODE", raising=False)

    assert WebSettings.from_env().admin_mode is False
