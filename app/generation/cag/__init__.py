"""Sistema de caché de estimaciones (exacta + semántica)."""

from app.generation.cag.exact import EstimationCache, EstimationExactCache
from app.generation.cag.keys import bucket_for_context, make_exact_key, output_format_for_bundle
from app.generation.cag.orchestrator import (
    EstimationCacheOrchestrator,
    build_cache_context,
    build_cache_orchestrator,
)
from app.generation.cag.semantic import EstimationSemanticCache
from app.generation.cag.telemetry import get_cache_metrics, reset_cache_metrics
from app.generation.cag.types import (
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
