"""Router HTTP para estimaciones (POST /estimate)."""

from __future__ import annotations

import asyncio
import hashlib
import time
from functools import partial

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_llm_wrapper
from app.logging.sync import run_sync_with_context
from app.prompts.registry import DEFAULT_ESTIMATION_BUNDLE
from app.schemas.estimation import EstimationRequest, EstimationResponse, TokenUsageResponse
from app.services.llm_service import build_estimation_cache_inputs
from app.services.llm_wrapper import LLMWrapper
from app.services.structured_llm import ReasoningLengthError

router = APIRouter(prefix="/api/v1", tags=["estimations"])
log = structlog.get_logger(__name__)


@router.post("/estimate", response_model=EstimationResponse)
async def create_estimation(
    request: EstimationRequest,
    settings: Settings = Depends(get_settings),
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EstimationResponse:
    """Genera una estimación estructurada y devuelve ``result`` + métricas."""
    log.info(
        "estimation_requested",
        log_category="business",
        project_type=request.project_type.value,
        detail_level=request.detail_level.value,
        description_sha256=hashlib.sha256(request.description.encode("utf-8")).hexdigest(),
    )

    opts = request.to_generation_options()
    system_prompt, user_message, model_used, max_tokens, thinking_budget, prompt_bundle = (
        build_estimation_cache_inputs(
            settings=settings,
            request=request,
            bundle=DEFAULT_ESTIMATION_BUNDLE,
        )
    )

    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    try:
        result, metrics = await run_sync_with_context(
            loop,
            None,
            partial(
                wrapper.generate_structured,
                system_prompt=system_prompt,
                user_message=user_message,
                detail_level=request.detail_level,
                model_override=opts.model,
                max_tokens=max_tokens,
                thinking_budget=thinking_budget,
                skip_cache=opts.skip_cache,
            ),
        )
    except ReasoningLengthError as exc:
        log.error(
            "estimation_validation_failed",
            log_category="business",
            error_recoverable=False,
            error_message=str(exc),
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        log.error(
            "estimation_failed",
            log_category="business",
            error_recoverable=False,
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=502, detail="Structured estimation failed") from exc

    duration_ms = int((time.perf_counter() - start) * 1000)

    log.info(
        "estimation_completed",
        log_category="business",
        cache_hit=bool(metrics["cache_hit"]),
        cost_usd=float(metrics["cost_usd"]),
        duration_ms=duration_ms,
        model=model_used,
        phase_count=len(result.phases),
        reasoning_chars=len(result.reasoning),
        confidence_pct=result.confidence_pct,
    )

    return EstimationResponse(
        result=result,
        prompt_version=prompt_bundle.public_id,
        prompt_version_created_at=prompt_bundle.created_at.isoformat(),
        model=str(metrics.get("model", model_used)),
        provider=str(metrics["provider"]),
        usage=TokenUsageResponse(**metrics["usage"]),
        cache_hit=bool(metrics["cache_hit"]),
        finish_reason=str(metrics.get("finish_reason", "stop")),
        cost_usd=float(metrics["cost_usd"]),
        response_seconds=time.perf_counter() - start,
    )
