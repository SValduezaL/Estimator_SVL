"""HTTP para el pipeline de embeddings (chunk → embed → stats)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import ALL_STRATEGIES, build_chunkers, get_chunker, get_embedder
from app.generation.rag.analysis.comparison import (
    ChunkingComparator,
    CompareRequest,
    CompareResponse,
)
from app.generation.rag.chunking.structural import JSONStructuralChunker
from app.generation.rag.embedding.embedder import OpenAIEmbedder, estimate_embedding_cost_usd
from app.generation.rag.schemas import IngestRequest, IngestResponse, IngestStats

log = structlog.get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

_INGEST_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "ingest_example_single_budget.json"
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
                "description": "Copia de ejemplo válida; también en data/ingest_example_single_budget.json",
                "value": _ingest_openapi_example(),
            }
        },
    ),
    chunker: JSONStructuralChunker = Depends(get_chunker),
    embedder: OpenAIEmbedder | None = Depends(get_embedder),
) -> IngestResponse:
    if embedder is None:
        log.error("embedding_ingest_failed", reason="embedder_unavailable")
        raise HTTPException(status_code=500, detail="Embedding service unavailable")

    try:
        chunks = chunker.chunk(request.budgets)
        embedded_chunks = embedder.embed_many(chunks)
    except ValueError as exc:
        log.warning("embedding_ingest_config_error", error_message=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("embedding_ingest_failed", error_type=type(exc).__name__)
        detail = "Embedding service unavailable"
        if get_settings().app_env == "dev":
            detail = f"{detail} ({type(exc).__name__}: {exc})"
        raise HTTPException(status_code=500, detail=detail) from exc

    total_tokens = sum(chunk.token_count for chunk in chunks)
    stats = IngestStats(
        total_budgets=len(request.budgets),
        total_chunks=len(embedded_chunks),
        total_tokens=total_tokens,
        estimated_cost_usd=estimate_embedding_cost_usd(total_tokens),
    )
    log.info(
        "embedding_ingest_completed",
        log_category="business",
        total_budgets=stats.total_budgets,
        total_chunks=stats.total_chunks,
        total_tokens=stats.total_tokens,
        estimated_cost_usd=stats.estimated_cost_usd,
    )
    return IngestResponse(chunks=embedded_chunks, stats=stats)


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
