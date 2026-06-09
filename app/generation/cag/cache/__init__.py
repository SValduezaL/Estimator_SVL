"""Sistema de caché de estimaciones (exacta + semántica)."""

from app.cache.exact import EstimationCache, EstimationExactCache
from app.cache.keys import bucket_for_context, make_exact_key, output_format_for_bundle
from app.cache.orchestrator import (
    EstimationCacheOrchestrator,
    build_cache_context,
    build_cache_orchestrator,
)
from app.cache.semantic import EstimationSemanticCache
from app.cache.telemetry import get_cache_metrics, reset_cache_metrics
from app.cache.types import (
    CachedPayload,
    CacheContext,
    CacheLookupResult,
    CacheSource,
)

__all__ = [
    "CachedPayload",
    "CacheContext",
    "CacheLookupResult",
    "CacheSource",
    "EstimationCache",
    "EstimationCacheOrchestrator",
    "EstimationExactCache",
    "EstimationSemanticCache",
    "bucket_for_context",
    "build_cache_context",
    "build_cache_orchestrator",
    "get_cache_metrics",
    "make_exact_key",
    "output_format_for_bundle",
    "reset_cache_metrics",
]
