"""Dependencias FastAPI reutilizables."""

from __future__ import annotations

from typing import Any

from fastapi import Depends

from app.cache import EstimationCacheOrchestrator, build_cache_orchestrator
from app.cache.exact import EstimationExactCache
from app.config import Settings, get_settings
from app.guardrails.pipeline import create_openai_client
from app.services.llm_wrapper import LLMWrapper

_orchestrator: EstimationCacheOrchestrator | None = None
_orchestrator_key: str | None = None


def _orchestrator_cache_key(settings: Settings) -> str:
    url = (settings.redis_url or "").strip()
    return (
        f"{url}|{settings.cache_ttl_seconds}|{settings.semantic_cache_enabled}|"
        f"{settings.semantic_cache_threshold}|{settings.semantic_cache_log_only}|"
        f"{settings.semantic_cache_index_name}|{settings.semantic_embedding_model}"
    )


def get_cache_orchestrator(
    settings: Settings = Depends(get_settings),
) -> EstimationCacheOrchestrator | None:
    global _orchestrator, _orchestrator_key
    url = (settings.redis_url or "").strip()
    if not url:
        return None
    key = _orchestrator_cache_key(settings)
    if _orchestrator is None or _orchestrator_key != key:
        _orchestrator = build_cache_orchestrator(settings, redis_client=None)
        _orchestrator_key = key
    return _orchestrator


def get_estimation_cache(
    orchestrator: EstimationCacheOrchestrator | None = Depends(get_cache_orchestrator),
) -> EstimationExactCache | None:
    """Compatibilidad: expone la capa exacta del orquestador."""
    if orchestrator is None:
        return None
    return orchestrator._exact


def get_llm_wrapper(
    settings: Settings = Depends(get_settings),
    orchestrator: EstimationCacheOrchestrator | None = Depends(get_cache_orchestrator),
) -> LLMWrapper:
    return LLMWrapper(settings, orchestrator=orchestrator)


def get_openai_moderation_client(
    settings: Settings = Depends(get_settings),
) -> Any | None:
    if not settings.guardrails_enabled or not settings.guardrails_moderation_enabled:
        return None
    return create_openai_client(settings)
