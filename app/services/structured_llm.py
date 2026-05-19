"""Completions estructuradas con Instructor + LiteLLM."""

from __future__ import annotations

from typing import Any, Callable

import instructor
import structlog
from litellm import completion
from app.schemas.estimation_common import REASONING_BOUNDS, DetailLevel
from app.schemas.estimation_output import EstimationResult

log = structlog.get_logger(__name__)

_instructor_direct = instructor.from_litellm(completion)


class ReasoningLengthError(ValueError):
    """``reasoning`` fuera del rango permitido para el ``detail_level`` solicitado."""


def assert_reasoning_length(result: EstimationResult, detail_level: DetailLevel) -> None:
    n = len(result.reasoning)
    lo, hi = REASONING_BOUNDS[detail_level.value]
    if not lo <= n <= hi:
        raise ReasoningLengthError(
            f"reasoning length {n} not in [{lo}, {hi}] for detail_level={detail_level.value!r}"
        )


def extract_metrics(raw: Any) -> dict[str, Any]:
    usage_obj = getattr(raw, "usage", None)
    inp = out = 0
    if usage_obj is not None:
        inp = int(getattr(usage_obj, "prompt_tokens", 0) or getattr(usage_obj, "input_tokens", 0) or 0)
        out = int(
            getattr(usage_obj, "completion_tokens", 0) or getattr(usage_obj, "output_tokens", 0) or 0
        )
    total = int(getattr(usage_obj, "total_tokens", 0) or (inp + out)) if usage_obj else inp + out
    choice = raw.choices[0] if getattr(raw, "choices", None) else None
    finish_reason = str(getattr(choice, "finish_reason", None) or "stop") if choice else "stop"
    model = str(getattr(raw, "model", "") or "")
    return {
        "usage": {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": total,
        },
        "usage_available": usage_obj is not None,
        "finish_reason": finish_reason,
        "model": model,
    }


def _reasoning_retry_message(detail_level: DetailLevel) -> str:
    lo, hi = REASONING_BOUNDS[detail_level.value]
    return (
        f'El campo "reasoning" debe tener entre {lo} y {hi} caracteres para '
        f'detail_level={detail_level.value!r}. Debe ser Markdown en español que '
        "justifique las decisiones (fases, tecnología, costes, plazo). "
        "No repitas la tabla de phases."
    )


def complete_estimation(
    *,
    client: Any,
    messages: list[dict[str, str]],
    model: str,
    api_key: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    num_retries: int,
    max_validation_retries: int,
    detail_level: DetailLevel,
    extra_kwargs: dict[str, Any] | None = None,
) -> tuple[EstimationResult, Any]:
    """Llama a Instructor y valida longitud de ``reasoning`` (con un reintento manual)."""
    base_kw: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "messages": messages,
        "response_model": EstimationResult,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout": timeout,
        "max_retries": max_validation_retries,
        "num_retries": num_retries,
    }
    if extra_kwargs:
        base_kw.update(extra_kwargs)

    result, raw = client.chat.completions.create_with_completion(**base_kw)
    try:
        assert_reasoning_length(result, detail_level)
        return result, raw
    except ReasoningLengthError as exc:
        log.warning(
            "reasoning_length_failed",
            log_category="technical",
            error_recoverable=True,
            detail_level=detail_level.value,
            reasoning_chars=len(result.reasoning),
            error_message=str(exc),
        )
        retry_messages = [
            *messages,
            {"role": "assistant", "content": result.model_dump_json()},
            {"role": "user", "content": _reasoning_retry_message(detail_level)},
        ]
        result2, raw2 = client.chat.completions.create_with_completion(
            **{**base_kw, "messages": retry_messages, "max_retries": 1},
        )
        assert_reasoning_length(result2, detail_level)
        return result2, raw2


def instructor_client_for_completion(
    completion_fn: Callable[..., Any],
) -> Any:
    return instructor.from_litellm(completion_fn)
