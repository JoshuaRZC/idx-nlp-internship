"""Runtime configuration for the Streamlit web application."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WebSettings:
    api_base_url: str = "http://127.0.0.1:8000"
    request_timeout_seconds: float = 30.0
    metrics_token: str = ""
    admin_mode: bool = False

    @classmethod
    def from_env(cls):
        return cls(
            api_base_url=os.getenv("API_BASE_URL", cls.api_base_url).rstrip("/"),
            request_timeout_seconds=float(
                os.getenv("WEB_REQUEST_TIMEOUT_SECONDS", cls.request_timeout_seconds)
            ),
            metrics_token=os.getenv("WEB_METRICS_TOKEN", cls.metrics_token),
            admin_mode=os.getenv("WEB_ADMIN_MODE", "false").lower() in {"1", "true", "yes"},
        )
