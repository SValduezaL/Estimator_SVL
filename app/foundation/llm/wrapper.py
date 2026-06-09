"""Cliente LLM unificado con LiteLLM: Router (fallback) y coste USD.

La orquestación de prompts CAG vive en ``app/prompts/``; la caché en ``app/cache/``.
Los precios USD por token están en ``llm_pricing.py``.
"""

from __future__ import annotations

import time
from typing import Any

import litellm
import structlog
from litellm import Router

from app.config import Settings
from app.guardrails.config import GUARDRAILS_VERSION
from app.guardrails.exceptions import OutputGuardrailRetryable
from app.guardrails.filters import build_safe_fallback
from app.guardrails.output import run_output_guardrails
from app.guardrails.telemetry import log_guardrail_event
from app.schemas.estimation_common import SCHEMA_VERSION, DetailLevel, ProjectType
from app.cache import EstimationCacheOrchestrator
from app.cache.policies import is_result_cacheable
from app.cache.types import CachedPayload, CacheContext
from app.schemas.estimation_output import EstimationResult
from app.services.llm_pricing import (
    estimate_cost_usd,
    normalise_model_name,
    provider_from_model,
)
from app.services.structured_llm import (
    complete_estimation,
    extract_metrics,
    instructor_client_for_completion,
)

log = structlog.get_logger(__name__)

CACHE_SCHEMA_VERSION = f"{SCHEMA_VERSION}:{GUARDRAILS_VERSION}"


def _usage_tokens(usage: Any) -> tuple[int, int, int]:
    if usage is None:
        return 0, 0, 0
    inp = int(getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0)
    out = int(getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0)
    tot = int(getattr(usage, "total_tokens", 0) or (inp + out))
    return inp, out, tot


def _cache_hit_metrics(cached: dict[str, Any], *, cache_key_model: str) -> dict[str, Any]:
    """Métricas al servir desde Redis: modelo y proveedor de la inferencia almacenada."""
    usage = cached.get(
        "usage",
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    )
    resolved_model = str(cached.get("model", cache_key_model))
    prov = str(cached.get("provider") or provider_from_model(resolved_model))
    return {
        "usage": dict(usage),
        "finish_reason": str(cached.get("finish_reason", "stop")),
        "cache_hit": True,
        "provider": prov,
        "model": resolved_model,
        "cost_usd": float(cached.get("cost_usd", 0.0)),
    }


class LLMWrapper:
    """LiteLLM + Router (fallback opcional) y tracking de coste."""

    def __init__(
        self,
        settings: Settings,
        orchestrator: EstimationCacheOrchestrator | None = None,
        *,
        cache: Any = None,  # compat tests antiguos; ignorado si hay orchestrator
    ) -> None:
        self._settings = settings
        self._orchestrator = orchestrator
        if cache is not None and orchestrator is None:
            from app.cache.exact import EstimationExactCache

            if isinstance(cache, EstimationExactCache):
                self._orchestrator = EstimationCacheOrchestrator(
                    settings=settings,
                    exact=cache,
                    semantic=None,
                    embedding_provider=None,
                )
        self._timeout = int(settings.llm_timeout_seconds)
        self._num_retries = int(settings.llm_num_retries)
        self._temperature = float(settings.temperature)
        self._primary_model = settings.llm_model
        self._fallback_model = (settings.llm_fallback_model or "").strip() or None

        primary_key = self._api_key_for_model(self._primary_model)
        if not primary_key:
            raise ValueError(
                f"No hay API key para el modelo principal {self._primary_model!r}."
            )

        primary_entry = {
            "model_name": "estimator",
            "litellm_params": {
                "model": self._primary_model,
                "api_key": primary_key,
                "timeout": self._timeout,
            },
        }
        model_list: list[dict[str, Any]] = [primary_entry]
        fallbacks: list[dict[str, list[str]]] = []

        if self._fallback_model:
            fb_key = self._api_key_for_model(self._fallback_model)
            if not fb_key:
                raise ValueError(
                    f"LLM_FALLBACK_MODEL={self._fallback_model!r} requiere la API key "
                    "del proveedor correspondiente."
                )
            model_list.append(
                {
                    "model_name": "estimator",
                    "litellm_params": {
                        "model": self._fallback_model,
                        "api_key": fb_key,
                        "timeout": self._timeout,
                    },
                }
            )
            fallbacks = [{"estimator": ["estimator"]}]

        router_kw: dict[str, Any] = {
            "model_list": model_list,
            "num_retries": self._num_retries,
        }
        if fallbacks:
            router_kw["fallbacks"] = fallbacks
        self.router = Router(**router_kw)
        self._instructor_direct = instructor_client_for_completion(litellm.completion)

        def _routed_completion(**kwargs: Any) -> Any:
            # Instructor pasa ``model`` en kwargs; el Router ya usa el alias ``estimator``.
            kwargs.pop("model", None)
            return self.router.completion(model="estimator", **kwargs)

        self._instructor_routed = instructor_client_for_completion(_routed_completion)

    def _api_key_for_model(self, model_id: str) -> str | None:
        prov = provider_from_model(model_id)
        if prov == "anthropic":
            return self._settings.anthropic_api_key
        if prov == "openai":
            return self._settings.openai_api_key
        return self._settings.openai_api_key or self._settings.anthropic_api_key

    def _build_call_kwargs(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int,
        thinking_budget: int | None,
        model_override: str | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self._temperature,
        }

        if thinking_budget is not None:
            target = model_override or self._primary_model
            if provider_from_model(target) == "anthropic":
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
                kwargs["max_tokens"] = max(max_tokens, thinking_budget + 1024)
            else:
                log.warning(
                    "thinking_budget_ignored_for_provider",
                    log_category="technical",
                    error_recoverable=True,
                    provider=provider_from_model(target),
                    model=target,
                )
        return kwargs

    def _dispatch(self, *, model_override: str | None, **kwargs: Any) -> Any:
        """Router (con fallback) o ``litellm.completion`` directo si hay override de modelo."""
        if model_override:
            api_key = self._api_key_for_model(model_override)
            if not api_key:
                raise ValueError(f"No hay API key para el modelo {model_override!r}.")
            return litellm.completion(
                model=model_override,
                api_key=api_key,
                timeout=self._timeout,
                num_retries=self._num_retries,
                **kwargs,
            )
        return self.router.completion(model="estimator", **kwargs)

    def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model_override: str | None = None,
        max_tokens: int | None = None,
        thinking_budget: int | None = None,
        skip_cache: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        """Genera una estimación completa con LiteLLM y caché exacta."""
        max_t = max_tokens if max_tokens is not None else self._settings.max_tokens
        cache_key_model = model_override or self._primary_model

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        kwargs = self._build_call_kwargs(
            messages=messages,
            max_tokens=max_t,
            thinking_budget=thinking_budget,
            model_override=model_override,
        )
        log.info(
            "llm_generate_started",
            log_category="technical",
            model=cache_key_model,
        )
        t0 = time.perf_counter()
        try:
            response = self._dispatch(model_override=model_override, **kwargs)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            log.error(
                "llm_generate_failed",
                log_category="technical",
                error_recoverable=False,
                error_type=type(exc).__name__,
                error_message=str(exc),
                latency_ms=latency_ms,
                model=cache_key_model,
                exc_info=True,
            )
            raise

        latency_ms = int((time.perf_counter() - t0) * 1000)
        choice = response.choices[0]
        rendered = (getattr(choice.message, "content", None) or "").strip()
        finish_reason = str(getattr(choice, "finish_reason", None) or "stop")
        input_tokens, output_tokens, total_tokens = _usage_tokens(getattr(response, "usage", None))
        log.info(
            "llm_generate_completed",
            log_category="technical",
            latency_ms=latency_ms,
            chars=len(rendered),
            model=cache_key_model,
            cache_hit=False,
        )

        resolved_model = normalise_model_name(cache_key_model)
        gen_provider = provider_from_model(resolved_model)
        gen_cost = estimate_cost_usd(resolved_model, input_tokens, output_tokens)

        return rendered, {
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            "cache_hit": False,
            "finish_reason": finish_reason,
            "provider": gen_provider,
            "cost_usd": gen_cost,
        }

    def _structured_metrics(
        self,
        raw: Any,
        *,
        cache_key_model: str,
        cache_hit: bool,
    ) -> dict[str, Any]:
        meta = extract_metrics(raw)
        resolved_model = normalise_model_name(meta.get("model") or cache_key_model)
        usage = meta["usage"]
        gen_provider = provider_from_model(resolved_model)
        gen_cost = estimate_cost_usd(
            resolved_model,
            int(usage["input_tokens"]),
            int(usage["output_tokens"]),
        )
        return {
            "usage": usage,
            "cache_hit": cache_hit,
            "finish_reason": str(meta["finish_reason"]),
            "provider": gen_provider,
            "cost_usd": gen_cost,
            "model": resolved_model,
        }

    def _call_structured(
        self,
        *,
        messages: list[dict[str, str]],
        model_id: str,
        model_override: str | None,
        max_tokens: int,
        thinking_budget: int | None,
        detail_level: DetailLevel,
        max_validation_retries: int = 2,
    ) -> tuple[EstimationResult, Any]:
        api_key = self._api_key_for_model(model_id)
        if not api_key:
            raise ValueError(f"No hay API key para el modelo {model_id!r}.")

        extra = self._build_call_kwargs(
            messages=messages,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
            model_override=model_override,
        )
        extra.pop("messages", None)
        client = self._instructor_direct if model_override else self._instructor_routed

        try:
            return complete_estimation(
                client=client,
                messages=messages,
                model=model_id if model_override else "estimator",
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=self._temperature,
                timeout=self._timeout,
                num_retries=self._num_retries,
                max_validation_retries=max_validation_retries,
                detail_level=detail_level,
                extra_kwargs=extra,
            )
        except Exception:
            if not model_override and self._fallback_model:
                fb_key = self._api_key_for_model(self._fallback_model)
                if fb_key:
                    log.warning(
                        "structured_fallback_model",
                        log_category="technical",
                        error_recoverable=True,
                        fallback_model=self._fallback_model,
                    )
                    fb_extra = self._build_call_kwargs(
                        messages=messages,
                        max_tokens=max_tokens,
                        thinking_budget=thinking_budget,
                        model_override=self._fallback_model,
                    )
                    fb_extra.pop("messages", None)
                    return complete_estimation(
                        client=self._instructor_direct,
                        messages=messages,
                        model=self._fallback_model,
                        api_key=fb_key,
                        max_tokens=max_tokens,
                        temperature=self._temperature,
                        timeout=self._timeout,
                        num_retries=self._num_retries,
                        max_validation_retries=max_validation_retries,
                        detail_level=detail_level,
                        extra_kwargs=fb_extra,
                    )
            raise

    def _apply_output_guardrails(
        self,
        result: EstimationResult,
        *,
        detail_level: DetailLevel,
        project_type: ProjectType,
        source_description: str,
    ) -> EstimationResult:
        return run_output_guardrails(
            result,
            settings=self._settings,
            detail_level=detail_level,
            project_type=project_type,
            description=source_description,
        )

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_message: str,
        detail_level: DetailLevel,
        project_type: ProjectType,
        source_description: str = "",
        model_override: str | None = None,
        max_tokens: int | None = None,
        thinking_budget: int | None = None,
        skip_cache: bool = False,
        max_validation_retries: int = 2,
        cache_context: CacheContext | None = None,
        cache_embedding: list[float] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[EstimationResult, dict[str, Any]]:
        """Genera ``EstimationResult`` validado vía Instructor + LiteLLM."""
        max_t = max_tokens if max_tokens is not None else self._settings.max_tokens
        cache_key_model = model_override or self._primary_model

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        log.info(
            "llm_structured_started",
            log_category="technical",
            model=cache_key_model,
            detail_level=detail_level.value,
        )
        t0 = time.perf_counter()
        max_out_retries = self._settings.guardrails_output_max_retries
        result: EstimationResult | None = None
        raw: Any = None
        used_safe_fallback = False
        try:
            for attempt in range(max_out_retries + 1):
                result, raw = self._call_structured(
                    messages=messages,
                    model_id=cache_key_model,
                    model_override=model_override,
                    max_tokens=max_t,
                    thinking_budget=thinking_budget,
                    detail_level=detail_level,
                    max_validation_retries=max_validation_retries,
                )
                try:
                    result = self._apply_output_guardrails(
                        result,
                        detail_level=detail_level,
                        project_type=project_type,
                        source_description=source_description,
                    )
                    break
                except OutputGuardrailRetryable as retry_exc:
                    if attempt >= max_out_retries:
                        log.warning(
                            "output_guardrail_retry_exhausted",
                            log_category="guardrails",
                            guardrail_name=retry_exc.guardrail_name,
                        )
                        result = build_safe_fallback(
                            project_type=project_type,
                            detail_level=detail_level,
                            reason=retry_exc.guardrail_name,
                        )
                        used_safe_fallback = True
                        break
                    log_guardrail_event(
                        "llm_retry_triggered",
                        guardrail_name=retry_exc.guardrail_name,
                        attempt=attempt + 1,
                    )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            log.error(
                "llm_structured_failed",
                log_category="technical",
                error_recoverable=False,
                error_type=type(exc).__name__,
                error_message=str(exc),
                latency_ms=latency_ms,
                model=cache_key_model,
                exc_info=True,
            )
            raise

        latency_ms = int((time.perf_counter() - t0) * 1000)
        metrics = self._structured_metrics(raw, cache_key_model=cache_key_model, cache_hit=False)
        metrics["cache_source"] = "none"
        log.info(
            "llm_structured_completed",
            log_category="technical",
            latency_ms=latency_ms,
            model=metrics["model"],
            cache_hit=False,
            phase_count=len(result.phases),
            reasoning_chars=len(result.reasoning),
            confidence_pct=result.confidence_pct,
        )

        if (
            self._orchestrator is not None
            and cache_context is not None
            and not skip_cache
        ):
            payload = CachedPayload(
                result=result,
                model=str(metrics["model"]),
                provider=str(metrics["provider"]),
                finish_reason=str(metrics["finish_reason"]),
                usage=dict(metrics["usage"]),
                cost_usd=float(metrics["cost_usd"]),
                latency_ms=latency_ms,
            )
            cacheable = is_result_cacheable(result) and not used_safe_fallback
            self._orchestrator.store(
                cache_context,
                payload,
                embedding=cache_embedding,
                cacheable=cacheable,
            )

        return result, metrics
