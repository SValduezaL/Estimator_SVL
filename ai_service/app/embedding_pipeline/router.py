"""HTTP routes for budget embedding ingest."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import structlog
from fastapi import APIRouter, Body, HTTPException

from ai_service.app.config import get_settings
from ai_service.app.embedding_pipeline.chunker import JSONStructuralChunker
from ai_service.app.embedding_pipeline.embedder import OpenAIEmbedder, estimate_embedding_cost_usd
from ai_service.app.embedding_pipeline.schemas import IngestRequest, IngestResponse, IngestStats

router = APIRouter(tags=["embeddings"])
log = structlog.get_logger(__name__)

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
                "description": (
                    "Copia de ejemplo válida; también en "
                    "ai_service/data/ingest_example_single_budget.json"
                ),
                "value": _ingest_openapi_example(),
            }
        },
    ),
) -> IngestResponse:
    """Chunk budgets by component and return vectorized chunks with aggregate stats."""
    chunker = JSONStructuralChunker()
    embedder = OpenAIEmbedder()

    try:
        chunks = chunker.chunk(request.budgets)
        embedded_chunks = embedder.embed_many(chunks)
    except ValueError as exc:
        log.warning(
            "embedding_ingest_config_error",
            log_category="technical",
            error_message=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        log.exception(
            "embedding_ingest_failed",
            log_category="technical",
            error_type=type(exc).__name__,
        )
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
