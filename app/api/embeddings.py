"""HTTP para el pipeline de embeddings (chunk → embed → persist)."""

from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import ALL_STRATEGIES, build_chunkers, get_chunker, get_db_session, get_embedder
from app.foundation.persistence.repositories import (
    create_document_with_chunks,
    get_document_by_source_path,
)
from app.generation.rag.analysis.comparison import (
    ChunkingComparator,
    CompareRequest,
    CompareResponse,
)
from app.generation.rag.chunking.structural import JSONStructuralChunker
from app.generation.rag.embedding.embedder import EMBEDDING_DIMENSIONS, OpenAIEmbedder
from app.generation.rag.schemas import Budget, IngestRequest, IngestResponse

log = structlog.get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

_INGEST_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "ingest_example_persist.json"
)


@lru_cache
def _ingest_openapi_example() -> dict:
    return json.loads(_INGEST_EXAMPLE_PATH.read_text(encoding="utf-8"))


@router.post("/ingest", response_model=IngestResponse)
async def ingest_embeddings(
    request: IngestRequest = Body(
        ...,
        openapi_examples={
            "fintech_single_budget": {
                "summary": "BUD-2024-014 — 4 components (FintechCorp)",
                "description": "Copia de ejemplo válida; también en data/ingest_example_persist.json",
                "value": _ingest_openapi_example(),
            }
        },
    ),
    chunker: JSONStructuralChunker = Depends(get_chunker),
    embedder: OpenAIEmbedder | None = Depends(get_embedder),
    session: AsyncSession = Depends(get_db_session),
) -> IngestResponse | JSONResponse:
    if embedder is None:
        log.error("embedding_ingest_failed", reason="embedder_unavailable")
        raise HTTPException(status_code=500, detail="Embedding service unavailable")

    t0 = time.perf_counter()
    try:
        async with session.begin():
            existing = await get_document_by_source_path(session, request.source_path)
            if existing is not None:
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": "Document already ingested",
                        "document_id": existing.id,
                    },
                )

            budget = Budget.model_validate(request.content)
            chunks = chunker.chunk([budget])
            embedded_chunks = embedder.embed_many(chunks)

            document_metadata = {
                "budget_id": budget.budget_id,
                "client_name": budget.client_metadata.name,
                "client_sector": budget.client_metadata.sector,
                "main_technology": budget.main_technology,
                "year": budget.year,
            }

            document_id, chunks_created = await create_document_with_chunks(
                session,
                source_path=request.source_path,
                document_type=request.document_type,
                document_metadata=document_metadata,
                embedded_chunks=embedded_chunks,
            )
    except ValueError as exc:
        log.warning("embedding_ingest_config_error", error_message=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("embedding_ingest_failed", error_type=type(exc).__name__)
        detail = "Embedding service unavailable"
        if get_settings().app_env == "dev":
            detail = f"{detail} ({type(exc).__name__}: {exc})"
        raise HTTPException(status_code=500, detail=detail) from exc

    ingestion_time_ms = int((time.perf_counter() - t0) * 1000)
    log.info(
        "embedding_ingest_completed",
        log_category="business",
        document_id=document_id,
        chunks_created=chunks_created,
        ingestion_time_ms=ingestion_time_ms,
    )
    return IngestResponse(
        document_id=document_id,
        chunks_created=chunks_created,
        embedding_dimension=EMBEDDING_DIMENSIONS,
        ingestion_time_ms=ingestion_time_ms,
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_embeddings(
    request: CompareRequest,
    embedder: OpenAIEmbedder | None = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> CompareResponse:
    if embedder is None:
        raise HTTPException(status_code=500, detail="Embedding service unavailable")

    names = request.strategies or ALL_STRATEGIES
    try:
        chunkers = build_chunkers(names, settings=settings)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {exc.args[0]}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    comparator = ChunkingComparator(chunkers, embedder)
    try:
        stats = comparator.compute_stats(request.budgets)
        queries = comparator.run_queries(request.budgets, request.queries, request.top_k)
    except Exception as exc:
        log.error("embeddings_compare_failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=500, detail="Failed to run chunking comparison") from exc

    return CompareResponse(stats_per_strategy=stats, queries_per_strategy=queries)
