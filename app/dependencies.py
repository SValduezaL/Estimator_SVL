"""Dependencias FastAPI reutilizables."""

from functools import lru_cache

from fastapi import Depends

from typing import Any

from app.config import Settings, get_settings
from app.guardrails.pipeline import create_openai_client
from app.services.llm_cache import EstimationCache
from app.services.llm_wrapper import LLMWrapper


@lru_cache
def _estimation_cache_for_url(url: str, ttl: int) -> EstimationCache:
    return EstimationCache.from_url(url, ttl=ttl)


def get_estimation_cache(settings: Settings = Depends(get_settings)) -> EstimationCache | None:
    url = (settings.redis_url or "").strip()
    if not url:
        return None
    return _estimation_cache_for_url(url, int(settings.cache_ttl_seconds))


def get_llm_wrapper(
    settings: Settings = Depends(get_settings),
    cache: EstimationCache | None = Depends(get_estimation_cache),
) -> LLMWrapper:
    return LLMWrapper(settings, cache)


def get_openai_moderation_client(
    settings: Settings = Depends(get_settings),
) -> Any | None:
    if not settings.guardrails_enabled or not settings.guardrails_moderation_enabled:
        return None
    return create_openai_client(settings)
