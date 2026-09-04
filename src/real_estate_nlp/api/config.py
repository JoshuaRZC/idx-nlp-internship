"""Environment-backed configuration for the API process."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    search_root: str = "data/models/search"
    intent_model_dir: str = "data/models/query_intent"
    redis_url: str = "redis://127.0.0.1:6379/0"
    cache_namespace: str = "real-estate-nlp-api-v1"
    search_cache_ttl_seconds: int = 120
    default_cache_ttl_seconds: int = 300
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 1

    @classmethod
    def from_env(cls):
        return cls(
            search_root=os.getenv("SEARCH_ROOT", cls.search_root),
            intent_model_dir=os.getenv("INTENT_MODEL_DIR", cls.intent_model_dir),
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            cache_namespace=os.getenv("API_CACHE_NAMESPACE", cls.cache_namespace),
            search_cache_ttl_seconds=int(
                os.getenv("API_SEARCH_CACHE_TTL_SECONDS", cls.search_cache_ttl_seconds)
            ),
            default_cache_ttl_seconds=int(
                os.getenv("API_CACHE_TTL_SECONDS", cls.default_cache_ttl_seconds)
            ),
            rate_limit_requests=int(
                os.getenv("API_RATE_LIMIT_REQUESTS", cls.rate_limit_requests)
            ),
            rate_limit_window_seconds=int(
                os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", cls.rate_limit_window_seconds)
            ),
        )
