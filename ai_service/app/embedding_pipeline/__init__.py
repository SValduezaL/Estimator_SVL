"""Pipeline de chunking y embeddings (S7)."""

from ai_service.app.embedding_pipeline.chunker import JSONStructuralChunker
from ai_service.app.embedding_pipeline.router import router as embeddings_router
from ai_service.app.embedding_pipeline.embedder import (
    EMBEDDING_COST_USD_PER_MILLION_TOKENS,
    EMBEDDING_MODEL,
    OpenAIEmbedder,
    estimate_embedding_cost_usd,
)
from ai_service.app.embedding_pipeline.schemas import (
    Budget,
    BudgetComponent,
    Chunk,
    EmbeddedChunk,
    IngestRequest,
    IngestResponse,
    IngestStats,
)

__all__ = [
    "Budget",
    "BudgetComponent",
    "Chunk",
    "EmbeddedChunk",
    "IngestRequest",
    "IngestResponse",
    "IngestStats",
    "JSONStructuralChunker",
    "EMBEDDING_MODEL",
    "EMBEDDING_COST_USD_PER_MILLION_TOKENS",
    "OpenAIEmbedder",
    "estimate_embedding_cost_usd",
    "embeddings_router",
]
