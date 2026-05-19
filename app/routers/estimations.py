"""Router HTTP para estimaciones (POST /estimate)."""

from __future__ import annotations

import asyncio
import time
from functools import partial

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.dependencies import get_llm_wrapper
from app.prompts.registry import DEFAULT_ESTIMATION_BUNDLE
from app.schemas.estimation import EstimationRequest, EstimationResponse, TokenUsageResponse
from app.services.llm_service import build_estimation_cache_inputs
from app.services.llm_wrapper import LLMWrapper

router = APIRouter(prefix="/api/v1", tags=["estimations"])


@router.post("/estimate", response_model=EstimationResponse)
async def create_estimation(
    request: EstimationRequest,
    settings: Settings = Depends(get_settings),
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EstimationResponse:
    """Genera una estimación y devuelve texto + métricas en JSON."""
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
    text, metrics = await loop.run_in_executor(
        None,
        partial(
            wrapper.generate,
            system_prompt=system_prompt,
            user_message=user_message,
            model_override=opts.model,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
            skip_cache=opts.skip_cache,
        ),
    )

    return EstimationResponse(
        text=text,
        prompt_version=prompt_bundle.public_id,
        prompt_version_created_at=prompt_bundle.created_at.isoformat(),
        model=model_used,
        provider=str(metrics["provider"]),
        usage=TokenUsageResponse(**metrics["usage"]),
        usage_available=bool(metrics["usage_available"]),
        cache_hit=bool(metrics["cache_hit"]),
        finish_reason=str(metrics.get("finish_reason", "stop")),
        cost_usd=float(metrics["cost_usd"]),
        response_seconds=time.perf_counter() - start,
    )
