"""Shim de compatibilidad — usar ``app.cache``."""

from app.cache.exact import EstimationCache, EstimationExactCache

__all__ = ["EstimationCache", "EstimationExactCache"]
