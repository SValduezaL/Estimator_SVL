"""Router HTTP para estimaciones (POST /estimate)."""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import replace
from functools import partial
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.cache import EstimationCacheOrchestrator
from app.cache.orchestrator import build_cache_context
from app.cache.types import CacheLookupResult
from app.config import Settings, get_settings
from app.dependencies import (
    get_async_openai_client,
    get_cache_orchestrator,
    get_llm_wrapper,
    get_openai_moderation_client,
)
from app.guardrails import run_input_guardrails, run_output_guardrails, validate_rendered_prompts
from app.guardrails.exceptions import GuardrailBlocked
from app.logging.sync import run_sync_with_context
from app.memory.exceptions import SessionExpiredError, SessionNotFoundError
from app.memory.service import (
    history_to_llm_messages,
    metadata_for_prompt,
    persist_estimation_turn,
)
from app.memory.store import get_session
from app.prompts.registry import DEFAULT_ESTIMATION_BUNDLE
from app.schemas.estimation import EstimationRequest, EstimationResponse, TokenUsageResponse
from app.services.llm_service import build_estimation_cache_inputs
from app.services.llm_wrapper import CACHE_SCHEMA_VERSION, LLMWrapper
from app.services.structured_llm import ReasoningLengthError

router = APIRouter(prefix="/api/v1", tags=["estimations"])
log = structlog.get_logger(__name__)


def _metrics_from_lookup(
    lookup: CacheLookupResult,
    *,
    cache_key_model: str,
) -> dict:
    base = lookup.to_metrics(cache_key_model=cache_key_model)
    if lookup.similarity is not None:
        base["semantic_similarity"] = lookup.similarity
    return base


@router.post("/estimate", response_model=EstimationResponse)
async def create_estimation(
    request: EstimationRequest,
    settings: Settings = Depends(get_settings),
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
    orchestrator: EstimationCacheOrchestrator | None = Depends(get_cache_orchestrator),
    openai_client=Depends(get_openai_moderation_client),
    metadata_client: Any | None = Depends(get_async_openai_client),
) -> EstimationResponse:
    """Genera una estimación estructurada y devuelve ``result`` + métricas."""
    log.info(
        "estimation_requested",
        log_category="business",
        project_type=request.project_type.value,
        detail_level=request.detail_level.value,
        session_id=request.session_id,
        description_sha256=hashlib.sha256(request.description.encode("utf-8")).hexdigest(),
    )

    session = None
    if request.session_id:
        try:
            session = get_session(request.session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SessionExpiredError as exc:
            raise HTTPException(status_code=410, detail=str(exc)) from exc

    try:
        input_guarded = run_input_guardrails(
            request.description,
            settings=settings,
            openai_client=openai_client,
        )
    except GuardrailBlocked as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    request_for_llm = request.model_copy(update={"description": input_guarded.text})
    opts = request.to_generation_options()
    if session is not None:
        opts = replace(opts, skip_cache=True)
    bundle = DEFAULT_ESTIMATION_BUNDLE
    model_used = opts.model if opts.model is not None else settings.llm_model
    max_tokens = opts.max_tokens if opts.max_tokens is not None else settings.max_tokens

    prompt_metadata = metadata_for_prompt(session.project_metadata) if session else None

    cache_ctx = build_cache_context(
        request=request_for_llm,
        bundle=bundle,
        schema_version=CACHE_SCHEMA_VERSION,
        model=model_used,
        max_tokens=max_tokens,
        thinking_budget=opts.thinking_budget,
        skip_cache=opts.skip_cache,
    )

    start = time.perf_counter()
    cache_embedding: list[float] | None = None

    if orchestrator is not None and session is None:
        lookup = orchestrator.lookup(cache_ctx)
        cache_embedding = lookup.embedding
        if lookup.hit and lookup.payload is not None:
            result = run_output_guardrails(
                lookup.payload.result,
                settings=settings,
                detail_level=request.detail_level,
                project_type=request.project_type,
                description=input_guarded.text,
            )
            metrics = _metrics_from_lookup(lookup, cache_key_model=model_used)
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.info(
                "estimation_completed",
                log_category="business",
                cache_hit=True,
                cache_source=metrics.get("cache_source"),
                cost_usd=float(metrics["cost_usd"]),
                duration_ms=duration_ms,
                model=model_used,
                phase_count=len(result.phases),
                session_id=request.session_id,
            )
            return EstimationResponse(
                result=result,
                prompt_version=bundle.public_id,
                prompt_version_created_at=bundle.created_at.isoformat(),
                model=str(metrics.get("model", model_used)),
                provider=str(metrics["provider"]),
                usage=TokenUsageResponse(**metrics["usage"]),
                cache_hit=True,
                finish_reason=str(metrics.get("finish_reason", "stop")),
                cost_usd=float(metrics["cost_usd"]),
                response_seconds=time.perf_counter() - start,
            )

    system_prompt, user_message, model_used, max_tokens, thinking_budget, prompt_bundle = (
        build_estimation_cache_inputs(
            settings=settings,
            request=request_for_llm,
            bundle=bundle,
            project_metadata=prompt_metadata,
        )
    )

    prompt_check = validate_rendered_prompts(
        system_prompt=system_prompt,
        user_message=user_message,
        settings=settings,
    )
    if not prompt_check.passed and prompt_check.policy.value == "exception":
        log.warning(
            "prompt_render_guardrail_failed",
            log_category="guardrails",
            message=prompt_check.message,
        )
        raise HTTPException(status_code=400, detail="Request could not be processed")

    conversation_history = history_to_llm_messages(session.history) if session else None

    loop = asyncio.get_running_loop()
    try:
        result, metrics = await run_sync_with_context(
            loop,
            None,
            partial(
                wrapper.generate_structured,
                system_prompt=system_prompt,
                user_message=user_message,
                detail_level=request.detail_level,
                project_type=request.project_type,
                source_description=input_guarded.text,
                model_override=opts.model,
                max_tokens=max_tokens,
                thinking_budget=thinking_budget,
                skip_cache=opts.skip_cache,
                cache_context=cache_ctx if session is None else None,
                cache_embedding=cache_embedding,
                conversation_history=conversation_history,
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

    if session is not None:
        await persist_estimation_turn(
            session,
            user_turn=input_guarded.text,
            result=result,
            client=metadata_client,
        )

    duration_ms = int((time.perf_counter() - start) * 1000)

    log.info(
        "estimation_completed",
        log_category="business",
        cache_hit=bool(metrics.get("cache_hit")),
        cache_source=metrics.get("cache_source"),
        cost_usd=float(metrics["cost_usd"]),
        duration_ms=duration_ms,
        model=model_used,
        phase_count=len(result.phases),
        reasoning_chars=len(result.reasoning),
        confidence_pct=result.confidence_pct,
        session_id=request.session_id,
    )

    return EstimationResponse(
        result=result,
        prompt_version=prompt_bundle.public_id,
        prompt_version_created_at=prompt_bundle.created_at.isoformat(),
        model=str(metrics.get("model", model_used)),
        provider=str(metrics["provider"]),
        usage=TokenUsageResponse(**metrics["usage"]),
        cache_hit=bool(metrics.get("cache_hit")),
        finish_reason=str(metrics.get("finish_reason", "stop")),
        cost_usd=float(metrics["cost_usd"]),
        response_seconds=time.perf_counter() - start,
    )
