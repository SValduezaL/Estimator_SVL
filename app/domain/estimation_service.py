"""Conductor del pipeline de estimación — único punto de composición entre capas."""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import replace
from functools import partial
from typing import Any

import structlog

from app.config import Settings
from app.domain.exceptions import EstimationFailedError, PromptGuardrailError
from app.domain.schemas.estimation import EstimationRequest, EstimationResponse, TokenUsageResponse
from app.domain.schemas.estimation_operations import (
    EstimationOperationsMetrics,
    OperationCosts,
    OperationUsage,
)
from app.foundation.guardrails import (
    run_input_guardrails,
    run_output_guardrails,
    validate_rendered_prompts,
)
from app.foundation.guardrails.exceptions import GuardrailBlocked
from app.foundation.llm.pricing import estimate_cost_usd
from app.foundation.llm.prompt_builder import build_estimation_cache_inputs
from app.foundation.llm.structured import ReasoningLengthError
from app.foundation.llm.wrapper import CACHE_SCHEMA_VERSION, LLMWrapper
from app.foundation.observability.sync import run_sync_with_context
from app.foundation.prompts.registry import DEFAULT_ESTIMATION_BUNDLE
from app.generation.cag import EstimationCacheOrchestrator
from app.generation.cag.orchestrator import build_cache_context
from app.generation.cag.types import CacheLookupResult
from app.generation.conversation.context_builder import compose_memory_context
from app.generation.conversation.exceptions import SessionExpiredError, SessionNotFoundError
from app.generation.conversation.service import metadata_for_prompt, persist_estimation_turn
from app.generation.conversation.store import get_session
from app.generation.conversation.tier_resolver import resolve_tier

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


def _embedding_lookup_cost_usd(description: str, settings: Settings) -> float:
    if not settings.semantic_cache_enabled:
        return 0.0
    tokens = max(8, len(description) // 4)
    return estimate_cost_usd(settings.semantic_embedding_model, tokens, 0)


def _build_operations_metrics(
    *,
    settings: Settings,
    estimation_cost_usd: float,
    extraction: dict[str, Any] | None = None,
    summary_compression: dict[str, Any] | None = None,
    tier_decision: dict[str, Any] | None = None,
    cache_lookup_performed: bool = False,
    cache_embedding_computed: bool = False,
    cache_hit: bool = False,
    cache_source: str | None = None,
    openai_client: Any | None = None,
) -> EstimationOperationsMetrics:
    ext = extraction or {}
    summary = summary_compression or {}
    mem_cost = float(ext.get("cost_usd", 0.0)) if ext.get("executed") else 0.0
    summary_cost = float(summary.get("cost_usd", 0.0)) if summary.get("executed") else 0.0
    guardrails_on = settings.guardrails_enabled
    moderation_on = guardrails_on and settings.guardrails_moderation_enabled
    moderation_ran = moderation_on and openai_client is not None

    return EstimationOperationsMetrics(
        costs=OperationCosts(
            estimation_usd=float(estimation_cost_usd),
            memory_extraction_usd=mem_cost,
            summary_compression_usd=summary_cost,
            guardrails_usd=0.0,
            cache_embedding_usd=0.0,
            total_usd=float(estimation_cost_usd) + mem_cost + summary_cost,
        ),
        memory_extraction=OperationUsage(
            input_tokens=int(ext.get("input_tokens", 0)),
            output_tokens=int(ext.get("output_tokens", 0)),
            total_tokens=int(ext.get("total_tokens", 0)),
            model=ext.get("model"),
            latency_ms=ext.get("latency_ms"),
        ),
        memory_extraction_executed=bool(ext.get("executed")),
        memory_extraction_degraded=bool(ext.get("degraded")),
        summary_compression=OperationUsage(
            input_tokens=int(summary.get("input_tokens", 0)),
            output_tokens=int(summary.get("output_tokens", 0)),
            total_tokens=int(summary.get("total_tokens", 0)),
            model=summary.get("model"),
            latency_ms=summary.get("latency_ms"),
        ),
        summary_compression_executed=bool(summary.get("executed")),
        summary_compression_degraded=bool(summary.get("degraded")),
        tier_decision=tier_decision,
        guardrails_enabled=guardrails_on,
        guardrails_moderation_executed=moderation_ran,
        semantic_cache_enabled=bool(
            settings.semantic_cache_enabled and (settings.redis_url or "").strip()
        ),
        cache_lookup_performed=cache_lookup_performed,
        cache_embedding_computed=cache_embedding_computed,
        cache_hit=cache_hit,
        cache_source=cache_source,
    )


class EstimationService:
    """Único punto de composición entre guardrails, caché, prompts, LLM y memoria."""

    def __init__(
        self,
        *,
        settings: Settings,
        wrapper: LLMWrapper,
        orchestrator: EstimationCacheOrchestrator | None,
        openai_client: Any | None,
        metadata_client: Any | None,
    ) -> None:
        self._settings = settings
        self._wrapper = wrapper
        self._orchestrator = orchestrator
        self._openai_client = openai_client
        self._metadata_client = metadata_client

    async def estimate(self, request: EstimationRequest) -> EstimationResponse:
        return await self._run_pipeline(request=request)

    async def _run_pipeline(self, *, request: EstimationRequest) -> EstimationResponse:
        settings = self._settings
        wrapper = self._wrapper
        orchestrator = self._orchestrator
        openai_client = self._openai_client
        metadata_client = self._metadata_client

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
            session = get_session(request.session_id)

        try:
            input_guarded = run_input_guardrails(
                request.description,
                settings=settings,
                openai_client=openai_client,
            )
        except GuardrailBlocked:
            raise

        request_for_llm = request.model_copy(update={"description": input_guarded.text})
        opts = request.to_generation_options()
        tier = resolve_tier(
            detail_level=request.detail_level,
            project_type=request.project_type,
            description=input_guarded.text,
        )
        if settings.tier_rules_enabled:
            opts = replace(
                opts,
                model=tier.model_override,
                max_tokens=tier.max_tokens,
                thinking_budget=tier.thinking_budget,
            )
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
        cache_lookup_performed = False
        cache_embedding_computed = False

        if orchestrator is not None and session is None:
            cache_lookup_performed = True
            lookup = orchestrator.lookup(cache_ctx)
            cache_embedding = lookup.embedding
            cache_embedding_computed = cache_embedding is not None
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
                resp_seconds = time.perf_counter() - start
                operations = _build_operations_metrics(
                    settings=settings,
                    estimation_cost_usd=float(metrics["cost_usd"]),
                    cache_lookup_performed=True,
                    cache_embedding_computed=cache_embedding_computed,
                    cache_hit=True,
                    cache_source=str(metrics.get("cache_source")),
                    openai_client=openai_client,
                )
                if cache_embedding_computed:
                    operations.costs.cache_embedding_usd = _embedding_lookup_cost_usd(
                        input_guarded.text,
                        settings,
                    )
                operations.costs.total_usd = (
                    operations.costs.estimation_usd
                    + operations.costs.memory_extraction_usd
                    + operations.costs.summary_compression_usd
                    + operations.costs.guardrails_usd
                    + operations.costs.cache_embedding_usd
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
                    response_seconds=resp_seconds,
                    operations=operations,
                )

        system_prompt, user_message, model_used, max_tokens, thinking_budget, prompt_bundle = (
            build_estimation_cache_inputs(
                settings=settings,
                request=request_for_llm,
                bundle=bundle,
                project_metadata=prompt_metadata,
                running_summary=(
                    session.running_summary.text
                    if session and session.running_summary
                    else None
                ),
                anchors=(
                    [a.fact for a in session.anchors if a.status == "active"]
                    if session
                    else None
                ),
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
            raise PromptGuardrailError("Request could not be processed")

        conversation_history = compose_memory_context(session) if session else None

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
            raise EstimationFailedError(str(exc)) from exc
        except Exception as exc:
            log.error(
                "estimation_failed",
                log_category="business",
                error_recoverable=False,
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            raise EstimationFailedError() from exc

        extraction_metrics: dict[str, Any] | None = None
        summary_metrics: dict[str, Any] | None = None
        if session is not None:
            persist_out = await persist_estimation_turn(
                session,
                user_turn=input_guarded.text,
                result=result,
                client=metadata_client,
                summary_model=settings.memory_summary_model,
            )
            if isinstance(persist_out, tuple) and len(persist_out) == 3:
                _, extraction_metrics, summary_metrics = persist_out
            else:
                _, extraction_metrics = persist_out
                summary_metrics = None

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

        resp_seconds = time.perf_counter() - start
        operations = _build_operations_metrics(
            settings=settings,
            estimation_cost_usd=float(metrics["cost_usd"]),
            extraction=extraction_metrics,
            summary_compression=summary_metrics,
            tier_decision={
                "tier": tier.tier.value,
                "rule_id": tier.rule_id,
                "reason_codes": tier.reason_codes,
            },
            cache_lookup_performed=cache_lookup_performed,
            cache_embedding_computed=cache_embedding_computed,
            cache_hit=bool(metrics.get("cache_hit")),
            cache_source=str(metrics.get("cache_source")) if metrics.get("cache_source") else None,
            openai_client=openai_client,
        )
        if cache_embedding_computed:
            operations.costs.cache_embedding_usd = _embedding_lookup_cost_usd(
                input_guarded.text,
                settings,
            )
        operations.costs.total_usd = (
            operations.costs.estimation_usd
            + operations.costs.memory_extraction_usd
            + operations.costs.summary_compression_usd
            + operations.costs.guardrails_usd
            + operations.costs.cache_embedding_usd
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
            response_seconds=resp_seconds,
            operations=operations,
        )


async def run_estimation_pipeline(
    *,
    request: EstimationRequest,
    settings: Settings,
    wrapper: LLMWrapper,
    orchestrator: EstimationCacheOrchestrator | None,
    openai_client: Any | None,
    metadata_client: Any | None,
) -> EstimationResponse:
    """Compatibilidad temporal para tests y callers legacy."""
    service = EstimationService(
        settings=settings,
        wrapper=wrapper,
        orchestrator=orchestrator,
        openai_client=openai_client,
        metadata_client=metadata_client,
    )
    return await service.estimate(request)
