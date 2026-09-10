from demo.config import DemoSettings


def test_demo_settings_reads_admin_mode_from_environment(monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_MODE", "true")

    assert DemoSettings.from_env().admin_mode is True


def test_demo_settings_keeps_admin_mode_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DEMO_ADMIN_MODE", raising=False)

    assert DemoSettings.from_env().admin_mode is False
