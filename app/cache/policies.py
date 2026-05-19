"""Políticas de lectura y escritura de caché."""

from __future__ import annotations

from app.cache.types import CacheContext
from app.config import Settings
from app.guardrails.filters import _NOT_ESTIMATED_PHASE
from app.schemas.estimation_common import LOW_CONFIDENCE_THRESHOLD, OUT_OF_SCOPE_PREFIX
from app.schemas.estimation_output import EstimationResult

_DEGRADED_REASONING_MARKER = "Estimación degradada por guardrails de salida."


def is_result_cacheable(result: EstimationResult) -> bool:
    """No cachear fallbacks degradados ni respuestas fuera de alcance."""
    if result.summary.startswith(OUT_OF_SCOPE_PREFIX):
        return False
    if _DEGRADED_REASONING_MARKER in result.reasoning:
        return False
    if any(p.name == _NOT_ESTIMATED_PHASE.name for p in result.phases):
        if result.confidence_pct < LOW_CONFIDENCE_THRESHOLD:
            return False
    return True


def should_read_cache(ctx: CacheContext, settings: Settings) -> bool:
    if ctx.skip_cache:
        return False
    if not (settings.redis_url or "").strip():
        return False
    return True


def should_write_exact(ctx: CacheContext, settings: Settings) -> bool:
    return should_read_cache(ctx, settings)


def should_write_semantic(ctx: CacheContext, settings: Settings) -> bool:
    if not should_read_cache(ctx, settings):
        return False
    return bool(settings.semantic_cache_enabled)
