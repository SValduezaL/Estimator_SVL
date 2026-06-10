"""Vector retrieval over persisted chunks (S8)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.foundation.persistence.models import Chunk


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    chunk_type: str
    content: str
    distance: float
    metadata: dict[str, Any]


async def search_chunks_by_cosine(
    session: AsyncSession,
    query_vector: list[float],
    k: int,
) -> list[RetrievedChunk]:
    distance_expr = Chunk.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.chunk_type,
            Chunk.content,
            Chunk.metadata_,
            distance_expr,
        )
        .where(Chunk.embedding.is_not(None))
        .order_by(distance_expr)
        .limit(k)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        RetrievedChunk(
            chunk_id=row.id,
            document_id=row.document_id,
            chunk_type=row.chunk_type,
            content=row.content,
            distance=float(row.distance),
            metadata=dict(row.metadata_ or {}),
        )
        for row in rows
    ]
