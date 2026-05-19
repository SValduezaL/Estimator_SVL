"""Caché Redis de coincidencia exacta para respuestas del estimador LLM.

La clave es SHA-256 del system prompt completo, el mensaje de usuario y los
parámetros de generación (modelo, max_tokens, thinking_budget).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis
import structlog

log = structlog.get_logger(__name__)


class EstimationCache:
    """Envoltorio fino sobre redis-py con clave determinista y TTL."""

    def __init__(self, redis_client: redis.Redis, ttl: int = 86400) -> None:
        self.redis = redis_client
        self.ttl = ttl

    @classmethod
    def from_url(cls, url: str, ttl: int = 86400) -> EstimationCache:
        return cls(redis.from_url(url, decode_responses=True), ttl=ttl)

    @staticmethod
    def make_key(
        *,
        system_prompt: str,
        user_message: str,
        model: str,
        max_tokens: int,
        thinking_budget: int | None,
        schema_version: str = "estimation.v1",
    ) -> str:
        payload = json.dumps(
            {
                "schema_version": schema_version,
                "system_prompt": system_prompt,
                "user_message": user_message,
                "model": model,
                "max_tokens": max_tokens,
                "thinking_budget": thinking_budget,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"estimation:{schema_version}:{digest}"

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            cached = self.redis.get(key)
        except redis.RedisError as exc:
            log.warning(
                "cache_get_failed",
                log_category="technical",
                error_recoverable=True,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            return None
        if cached:
            log.info(
                "cache_hit",
                log_category="technical",
                key_prefix=key[:24],
            )
            return json.loads(cached)
        log.info(
            "cache_miss",
            log_category="technical",
            key_prefix=key[:24],
        )
        return None

    def set(self, key: str, response: dict[str, Any]) -> None:
        try:
            self.redis.setex(key, self.ttl, json.dumps(response))
            log.info(
                "cache_stored",
                log_category="technical",
                key_prefix=key[:24],
                ttl=self.ttl,
            )
        except redis.RedisError as exc:
            log.warning(
                "cache_set_failed",
                log_category="technical",
                error_recoverable=True,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
