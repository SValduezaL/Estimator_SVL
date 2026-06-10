"""Data access helpers for document/chunk persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.foundation.persistence.models import Chunk, Document
from app.generation.rag.schemas import EmbeddedChunk

BUDGET_COMPONENT_CHUNK_TYPE = "budget_component"


async def get_document_by_source_path(
    session: AsyncSession,
    source_path: str,
) -> Document | None:
    stmt = select(Document).where(Document.source_path == source_path)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_document_with_chunks(
    session: AsyncSession,
    *,
    source_path: str,
    document_type: str,
    document_metadata: dict[str, Any],
    embedded_chunks: list[EmbeddedChunk],
) -> tuple[int, int]:
    document = Document(
        source_path=source_path,
        document_type=document_type,
        metadata_=document_metadata,
    )
    session.add(document)
    await session.flush()

    chunk_rows = [
        Chunk(
            document_id=document.id,
            chunk_type=BUDGET_COMPONENT_CHUNK_TYPE,
            content=embedded.text,
            embedding=embedded.embedding,
            metadata_=embedded.metadata,
        )
        for embedded in embedded_chunks
    ]
    session.add_all(chunk_rows)
    await session.flush()

    return document.id, len(chunk_rows)
