"""Estrategias de chunking para RAG."""

from app.generation.rag.chunking.base import Chunker
from app.generation.rag.chunking.structural import JSONStructuralChunker

__all__ = ["Chunker", "JSONStructuralChunker"]
