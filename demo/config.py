"""Runtime configuration for the Streamlit demo."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoSettings:
    api_base_url: str = "http://127.0.0.1:8000"
    request_timeout_seconds: float = 30.0
    metrics_token: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            api_base_url=os.getenv("API_BASE_URL", cls.api_base_url).rstrip("/"),
            request_timeout_seconds=float(
                os.getenv("DEMO_REQUEST_TIMEOUT_SECONDS", cls.request_timeout_seconds)
            ),
            metrics_token=os.getenv("DEMO_METRICS_TOKEN", cls.metrics_token),
        )
