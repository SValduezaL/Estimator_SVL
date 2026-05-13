"""Router HTTP para estimaciones (solo streaming SSE en POST /estimate)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from functools import partial

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.config import Settings, get_settings
from app.dependencies import get_llm_wrapper
from app.schemas.estimation import ESTIMATION_PROMPT_VERSION, EstimationRequest
from app.services.llm_service import build_estimation_cache_inputs
from app.services.llm_wrapper import LLMWrapper

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["estimations"])

_SENT = object()


@router.post("/estimate")
async def create_estimation_stream(
    request: EstimationRequest,
    settings: Settings = Depends(get_settings),
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EventSourceResponse:
    """Streaming SSE: eventos ``token`` (texto), ``metrics`` (JSON) y ``done``."""
    opts = request.to_generation_options()
    system_prompt, user_message, model_used, max_tokens, thinking_budget = build_estimation_cache_inputs(
        settings=settings,
        description=request.description,
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
                    model_override=opts.model,
                    max_tokens=max_tokens,
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
                    payload["prompt_version"] = ESTIMATION_PROMPT_VERSION
                    yield {"event": "metrics", "data": json.dumps(payload, ensure_ascii=False)}
                    yield {"event": "done", "data": "[DONE]"}
        except Exception as exc:  # pragma: no cover - defensa streaming
            log.exception("estimate_stream_failed")
            yield {"event": "error", "data": str(exc)}

    return EventSourceResponse(event_generator())
