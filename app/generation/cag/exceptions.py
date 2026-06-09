"""Excepciones del subsistema de caché (degradación graceful)."""

from __future__ import annotations


class CacheError(Exception):
    """Error base de caché."""


class EmbeddingError(CacheError):
    """Fallo al generar embeddings."""


class SemanticCacheError(CacheError):
    """Fallo en índice o consulta vectorial."""
