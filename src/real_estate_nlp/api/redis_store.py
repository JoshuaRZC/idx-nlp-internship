"""Small Redis adapter for response caching and distributed rate limiting."""

from __future__ import annotations

import hashlib
import json
import time
import uuid


class RedisStore:
    RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    return {0, tonumber(oldest[2]) + window - now}
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
return {1, 0}
"""

    def __init__(self, client, namespace="real-estate-nlp-api-v1"):
        self.client = client
        self.namespace = namespace

    @classmethod
    def from_url(cls, url, namespace):
        import redis

        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        return cls(client, namespace=namespace)

    def ping(self):
        return self.client.ping()

    def close(self):
        self.client.close()

    def get_json(self, key):
        value = self.client.get(key)
        return json.loads(value) if value else None

    def set_json(self, key, value, ttl_seconds):
        self.client.set(key, json.dumps(value, separators=(",", ":")), ex=ttl_seconds)

    def cache_key(self, endpoint, payload, version="default"):
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        return f"{self.namespace}:cache:{version}:{endpoint}:{digest}"

    def allow_request(self, client_ip, limit, window_seconds):
        now_ms = int(time.time() * 1000)
        window_ms = window_seconds * 1000
        ip_digest = hashlib.sha256(client_ip.encode()).hexdigest()[:24]
        key = f"{self.namespace}:rate:{ip_digest}"
        allowed, retry_after_ms = self.client.eval(
            self.RATE_LIMIT_SCRIPT,
            1,
            key,
            now_ms,
            window_ms,
            limit,
            f"{now_ms}:{uuid.uuid4().hex}",
        )
        return bool(allowed), max(0, int(retry_after_ms))
