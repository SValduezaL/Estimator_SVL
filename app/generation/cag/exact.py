"""Caché Redis de coincidencia exacta (v2 pre-render)."""

from __future__ import annotations

import json
from typing import Any

import redis
import structlog

from app.generation.cag.keys import make_exact_key
from app.generation.cag.telemetry import increment_cache_metric, log_cache_event
from app.generation.cag.types import CachedPayload, CacheContext, CacheLookupResult, CacheSource

log = structlog.get_logger(__name__)


class EstimationExactCache:
    """Envoltorio fino sobre redis-py con clave determinista v2 y TTL."""

    def __init__(self, redis_client: redis.Redis, ttl: int = 86400) -> None:
        self.redis = redis_client
        self.ttl = ttl

    @classmethod
    def from_url(cls, url: str, ttl: int = 86400) -> EstimationExactCache:
        return cls(redis.from_url(url, decode_responses=True), ttl=ttl)

    def lookup(self, ctx: CacheContext) -> CacheLookupResult:
        key = make_exact_key(ctx)
        try:
            cached = self.redis.get(key)
        except redis.RedisError as exc:
            log_cache_event(
                "cache_get_failed",
                error_recoverable=True,
                error_type=type(exc).__name__,
                error_message=str(exc),
                key_prefix=key[:32],
            )
            return CacheLookupResult(hit=False)

        if not cached:
            log_cache_event("cache_miss", key_prefix=key[:32], cache_layer="exact")
            increment_cache_metric("exact_cache", "miss")
            return CacheLookupResult(hit=False)

        try:
            data = json.loads(cached)
            payload = CachedPayload.from_redis_dict(data)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            log_cache_event(
                "cache_get_failed",
                error_recoverable=True,
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
                key_prefix=key[:32],
            )
            increment_cache_metric("exact_cache", "corrupt")
            return CacheLookupResult(hit=False)

        log_cache_event("cache_hit", key_prefix=key[:32], cache_layer="exact")
        increment_cache_metric("exact_cache", "hit")
        return CacheLookupResult(
            hit=True,
            source=CacheSource.EXACT,
            payload=payload,
        )

    def store(self, ctx: CacheContext, payload: CachedPayload) -> None:
        key = make_exact_key(ctx)
        try:
            self.redis.setex(key, self.ttl, json.dumps(payload.to_redis_dict()))
            log_cache_event(
                "cache_stored",
                key_prefix=key[:32],
                ttl=self.ttl,
                cache_layer="exact",
            )
            increment_cache_metric("exact_cache", "stored")
        except redis.RedisError as exc:
            log_cache_event(
                "cache_set_failed",
                error_recoverable=True,
                error_type=type(exc).__name__,
                error_message=str(exc),
                key_prefix=key[:32],
            )


# Alias retrocompatible para tests e imports existentes
EstimationCache = EstimationExactCache
