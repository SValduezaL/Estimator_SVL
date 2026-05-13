"""Cliente LLM unificado con LiteLLM: Router (fallback), caché exacta y coste USD.

La orquestación de prompts CAG sigue en ``llm_service.py``; este módulo se limita a
``completion`` / streaming y Redis. Los precios USD por token están en ``llm_pricing.py``.
Sin structlog (``logging`` estándar).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterator

import litellm
from litellm import Router

from app.config import Settings
from app.services.llm_cache import EstimationCache, chunk_text_for_sse
from app.services.llm_pricing import (
    estimate_cost_usd,
    normalise_model_name,
    provider_from_model,
)
from app.services.llm_service import StreamEvent

log = logging.getLogger(__name__)


def _extract_delta(chunk: Any) -> str:
    """Extrae el delta de texto de un chunk de streaming (formato OpenAI-compatible)."""
    try:
        delta = chunk.choices[0].delta
    except (AttributeError, IndexError, TypeError):
        return ""
    content = getattr(delta, "content", None)
    return content or ""


def _usage_tokens(usage: Any) -> tuple[int, int, int]:
    if usage is None:
        return 0, 0, 0
    inp = int(getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0)
    out = int(getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0)
    tot = int(getattr(usage, "total_tokens", 0) or (inp + out))
    return inp, out, tot


class LLMWrapper:
    """LiteLLM + Router (fallback opcional), caché exacta y tracking de coste."""

    def __init__(
        self,
        settings: Settings,
        cache: EstimationCache | None = None,
    ) -> None:
        self._settings = settings
        self._cache = cache
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
        stream: bool,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self._temperature,
        }
        if stream:
            kwargs["stream"] = True
            if provider_from_model(model_override or self._primary_model) == "openai":
                kwargs["stream_options"] = {"include_usage": True}

        if thinking_budget is not None:
            target = model_override or self._primary_model
            if provider_from_model(target) == "anthropic":
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
                kwargs["max_tokens"] = max(max_tokens, thinking_budget + 1024)
            else:
                log.warning(
                    "thinking_budget_ignored_for_provider provider=%s model=%s",
                    provider_from_model(target),
                    target,
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

    def stream_events(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model_override: str | None = None,
        max_tokens: int | None = None,
        thinking_budget: int | None = None,
        skip_cache: bool = False,
    ) -> Iterator[StreamEvent]:
        """Eventos chunk + done (métricas) con LiteLLM streaming y caché exacta."""
        max_t = max_tokens if max_tokens is not None else self._settings.max_tokens
        cache_key_model = model_override or self._primary_model
        cache_key: str | None = None

        if self._cache is not None and not skip_cache:
            cache_key = EstimationCache.make_key(
                system_prompt=system_prompt,
                user_message=user_message,
                model=cache_key_model,
                max_tokens=max_t,
                thinking_budget=thinking_budget,
            )
            cached = self._cache.get(cache_key)
            if cached:
                full = str(cached.get("estimation", ""))
                log.info("stream_cache_hit chars=%s", len(full))
                for piece in chunk_text_for_sse(full):
                    yield StreamEvent(type="chunk", data={"text": piece})
                usage = cached.get(
                    "usage",
                    {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                )
                prov = str(cached.get("provider") or provider_from_model(str(cached.get("model", cache_key_model))))
                yield StreamEvent(
                    type="done",
                    data={
                        "usage": dict(usage),
                        "usage_available": True,
                        "finish_reason": str(cached.get("finish_reason", "stop")),
                        "cache_hit": True,
                        "provider": prov,
                        "cost_usd": float(cached.get("cost_usd", 0.0)),
                    },
                )
                return

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        kwargs = self._build_call_kwargs(
            messages=messages,
            max_tokens=max_t,
            thinking_budget=thinking_budget,
            model_override=model_override,
            stream=True,
        )
        log.info("llm_stream_started model=%s", cache_key_model)
        t0 = time.perf_counter()
        full_text: list[str] = []
        input_tokens = 0
        output_tokens = 0
        usage_available = False
        try:
            stream = self._dispatch(model_override=model_override, **kwargs)
            for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    input_tokens, output_tokens, _ = _usage_tokens(usage)
                    usage_available = True
                delta = _extract_delta(chunk)
                if delta:
                    full_text.append(delta)
                    yield StreamEvent(type="chunk", data={"text": delta})
        except Exception as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            log.error(
                "llm_stream_failed error_type=%s error=%s latency_ms=%s",
                type(exc).__name__,
                exc,
                latency_ms,
            )
            raise

        latency_ms = int((time.perf_counter() - t0) * 1000)
        rendered = "".join(full_text)
        log.info("llm_stream_completed latency_ms=%s chars=%s", latency_ms, len(rendered))

        resolved_model = normalise_model_name(cache_key_model)
        stream_provider = provider_from_model(resolved_model)
        stream_cost = estimate_cost_usd(resolved_model, input_tokens, output_tokens)

        if self._cache is not None and cache_key is not None and not skip_cache:
            self._cache.set(
                cache_key,
                {
                    "estimation": rendered,
                    "model": resolved_model,
                    "provider": stream_provider,
                    "finish_reason": "stop",
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                    "latency_ms": latency_ms,
                    "cost_usd": stream_cost,
                },
            )

        yield StreamEvent(
            type="done",
            data={
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                "usage_available": usage_available,
                "cache_hit": False,
                "finish_reason": "stop",
                "provider": stream_provider,
                "cost_usd": stream_cost,
            },
        )
