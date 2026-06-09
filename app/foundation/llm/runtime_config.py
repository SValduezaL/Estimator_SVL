"""Configuración de modelos mutable en runtime, respaldada por Redis."""

from __future__ import annotations

import redis
import structlog

from app.config import Settings

log = structlog.get_logger()

MODEL_KEYS: tuple[str, ...] = (
    "PRIMARY_MODEL",
    "FALLBACK_MODEL",
    "CRITIC_MODEL",
    "METADATA_EXTRACTOR_MODEL",
    "COMPRESSION_MODEL",
    "PROPOSITIONAL_CHUNKER_MODEL",
    "CONTEXTUAL_CHUNKER_MODEL",
)

MODEL_KEY_TO_SETTINGS: dict[str, str] = {
    "PRIMARY_MODEL": "llm_model",
    "FALLBACK_MODEL": "llm_fallback_model",
    "CRITIC_MODEL": "llm_model",
    "METADATA_EXTRACTOR_MODEL": "memory_summary_model",
    "COMPRESSION_MODEL": "memory_summary_model",
    "PROPOSITIONAL_CHUNKER_MODEL": "llm_model",
    "CONTEXTUAL_CHUNKER_MODEL": "llm_model",
}

HASH_KEY = "estimator:runtime_config"


class RuntimeConfigUnavailable(Exception):
    """Fallo al escribir overrides (Redis no disponible)."""


class RuntimeModelConfig:
    """Store de overrides en hash Redis para knobs de modelo LLM."""

    def __init__(self, redis_client: redis.Redis, settings: Settings) -> None:
        self._redis = redis_client
        self._settings = settings

    @classmethod
    def from_url(cls, url: str, settings: Settings) -> "RuntimeModelConfig":
        return cls(redis.from_url(url, decode_responses=True), settings)

    def get(self, key: str) -> str | None:
        self._validate_key(key)
        try:
            return self._redis.hget(HASH_KEY, key)
        except redis.RedisError as exc:
            log.warning("runtime_config_read_failed", key=key, error=str(exc)[:200])
            return None

    def set(self, key: str, value: str | None) -> None:
        self._validate_key(key)
        try:
            if value is None:
                self._redis.hdel(HASH_KEY, key)
            else:
                self._redis.hset(HASH_KEY, key, value)
        except redis.RedisError as exc:
            raise RuntimeConfigUnavailable(str(exc)) from exc

    def effective(self, key: str) -> str:
        return self.get(key) or self.default(key)

    def default(self, key: str) -> str:
        self._validate_key(key)
        attr = MODEL_KEY_TO_SETTINGS[key]
        value = getattr(self._settings, attr)
        return str(value) if value is not None else ""

    def is_overridden(self, key: str) -> bool:
        return self.get(key) is not None

    def snapshot(self) -> dict[str, dict[str, str | bool]]:
        try:
            overrides = self._redis.hgetall(HASH_KEY)
        except redis.RedisError as exc:
            log.warning("runtime_config_read_failed", key="*", error=str(exc)[:200])
            overrides = {}
        return {
            key: {
                "effective": overrides.get(key) or self.default(key),
                "default": self.default(key),
                "overridden": key in overrides,
            }
            for key in MODEL_KEYS
        }

    def reset_all(self) -> None:
        try:
            self._redis.delete(HASH_KEY)
        except redis.RedisError as exc:
            raise RuntimeConfigUnavailable(str(exc)) from exc

    @staticmethod
    def _validate_key(key: str) -> None:
        if key not in MODEL_KEYS:
            raise ValueError(f"Unknown model key: {key}")
