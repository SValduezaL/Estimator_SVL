"""Semantic search over persisted budget chunks."""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_embedder
from app.generation.rag.embedding.embedder import OpenAIEmbedder
from app.generation.rag.retrieval import search_chunks_by_cosine
from app.generation.rag.schemas import SearchRequest, SearchResponse, SearchResult

log = structlog.get_logger()

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    embedder: OpenAIEmbedder | None = Depends(get_embedder),
) -> SearchResponse:
    if embedder is None:
        raise HTTPException(status_code=500, detail="Embedding service unavailable")

    t0 = time.perf_counter()
    try:
        query_vector = embedder.embed_one(request.query)
        hits = await search_chunks_by_cosine(session, query_vector, request.k)
    except Exception as exc:
        log.exception("semantic_search_failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail="Semantic search failed") from exc

    search_time_ms = int((time.perf_counter() - t0) * 1000)
    results = [
        SearchResult(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            chunk_type=hit.chunk_type,
            content=hit.content,
            distance=round(hit.distance, 4),
            metadata=hit.metadata,
        )
        for hit in hits
    ]
    log.info(
        "semantic_search_completed",
        log_category="business",
        k=request.k,
        results_count=len(results),
        search_time_ms=search_time_ms,
    )
    return SearchResponse(
        query=request.query,
        k=request.k,
        search_time_ms=search_time_ms,
        results=results,
    )
