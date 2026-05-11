"""Router HTTP para estimaciones."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from functools import partial

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse

from app.config import Settings, get_settings
from app.dependencies import get_llm_wrapper
from app.schemas.estimation import (
    EstimationRequest,
    EstimationResponse,
    StreamEstimationRequest,
    TokenUsage,
    structure_result_to_schema,
)
from app.services.evaluation import evaluate_estimation_structure
from app.services.llm_service import (
    LLMServiceError,
    build_estimation_cache_inputs,
    generate_estimation,
)
from app.services.llm_wrapper import LLMWrapper

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["estimations"])

_SENT = object()


def _ensure_model_allowed(settings: Settings, model: str | None) -> None:
    if model is None:
        return
    allowed = settings.llm_models_by_provider[settings.llm_provider]
    if model not in allowed:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Modelo no permitido para el proveedor actual: {model!r}. "
                f"Válidos: {sorted(allowed)}"
            ),
        )


@router.post("/estimate", response_model=EstimationResponse)
async def create_estimation(
    request: EstimationRequest,
    settings: Settings = Depends(get_settings),
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EstimationResponse:
    """Recibe una transcripción y devuelve estimación con opciones de generación."""
    _ensure_model_allowed(settings, request.model)
    opts = request.to_generation_options()
    try:
        raw = await run_in_threadpool(
            generate_estimation,
            request.transcription,
            opts,
            settings=settings,
            llm_wrapper=wrapper,
        )
    except LLMServiceError as exc:
        log.error("estimation_endpoint_error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    validation = None
    if request.evaluate:
        val = evaluate_estimation_structure(
            str(raw["estimation"]),
            finish_reason=str(raw["finish_reason"]),
        )
        validation = structure_result_to_schema(val)

    usage_raw = raw["usage"]
    cache_hit = bool(raw.get("cache_hit", False))
    return EstimationResponse(
        estimation=str(raw["estimation"]),
        model=str(raw["model"]),
        provider=str(raw.get("provider", settings.llm_provider)),
        finish_reason=str(raw["finish_reason"]),
        preprocessing=request.preprocessing,
        usage=TokenUsage(
            input_tokens=int(usage_raw["input_tokens"]),
            output_tokens=int(usage_raw["output_tokens"]),
            total_tokens=int(usage_raw["total_tokens"]),
        ),
        validation=validation,
        cache_hit=cache_hit,
        cost_usd=float(raw.get("cost_usd", 0.0)),
    )


@router.post("/estimate/stream")
async def create_estimation_stream(
    request: StreamEstimationRequest,
    settings: Settings = Depends(get_settings),
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EventSourceResponse:
    """Streaming tipo SSE: eventos token (texto), metrics (JSON, incluye cache_hit) y done."""
    _ensure_model_allowed(settings, request.model)
    opts = request.to_generation_options()
    system_prompt, user_message, model_used, max_tokens, thinking_budget = build_estimation_cache_inputs(
        settings=settings,
        transcription=request.transcription,
        opts=opts,
    )

    async def event_generator() -> AsyncIterator[dict]:
        loop = asyncio.get_running_loop()
        start = time.perf_counter()
        try:
            stream_it = iter(
                wrapper.stream_events(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    model_override=request.model,
                    max_tokens=request.max_tokens,
                    thinking_budget=thinking_budget,
                    skip_cache=opts.skip_cache,
                )
            )
            while True:
                ev = await loop.run_in_executor(None, partial(next, stream_it, _SENT))
                if ev is _SENT:
                    break
                if ev.type == "chunk":
                    text = ev.data.get("text")
                    if text:
                        yield {"event": "token", "data": text}
                elif ev.type == "done":
                    payload = dict(ev.data)
                    payload["model"] = model_used
                    if "finish_reason" not in payload:
                        payload["finish_reason"] = "stop"
                    payload["response_seconds"] = time.perf_counter() - start
                    yield {"event": "metrics", "data": json.dumps(payload, ensure_ascii=False)}
                    yield {"event": "done", "data": "[DONE]"}
        except Exception as exc:  # pragma: no cover - defensa streaming
            log.exception("estimate_stream_failed")
            yield {"event": "error", "data": str(exc)}

    return EventSourceResponse(event_generator())
