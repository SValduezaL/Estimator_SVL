"""Persistencia SQLAlchemy + pgvector (Sesión 8)."""

from app.foundation.persistence.database import get_async_session, get_engine, get_session_factory
from app.foundation.persistence.models import Base, Chunk, Document, EMBEDDING_DIMENSIONS

__all__ = [
    "Base",
    "Chunk",
    "Document",
    "EMBEDDING_DIMENSIONS",
    "get_async_session",
    "get_engine",
    "get_session_factory",
]
