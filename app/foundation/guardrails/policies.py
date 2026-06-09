"""Políticas de fallo explícitas para cada guardrail."""

from __future__ import annotations

from app.guardrails.exceptions import (
    GuardrailBlocked,
    InputGuardrailViolation,
    OutputGuardrailRetryable,
)
from app.guardrails.types import FailurePolicy, GuardrailCheckResult, InputViolationReason


def apply_input_policy(
    check: GuardrailCheckResult,
    *,
    text: str,
    reason: InputViolationReason,
) -> str:
    """Aplica la política de una capa de entrada; devuelve texto (posiblemente filtrado)."""
    if check.passed:
        return text

    if check.policy == FailurePolicy.LOG_ONLY:
        return text

    if check.policy == FailurePolicy.FILTER:
        return check.filtered_text or text

    if check.policy == FailurePolicy.EXCEPTION:
        raise InputGuardrailViolation(
            check.message or f"Input blocked by {check.name}",
            reason=reason,
        )

    raise InputGuardrailViolation(
        check.message or f"Input blocked by {check.name}",
        reason=reason,
    )


def apply_output_policy(check: GuardrailCheckResult) -> None:
    """Aplica política de salida; FILTER se maneja en el orquestador."""
    if check.passed:
        return

    if check.policy == FailurePolicy.LOG_ONLY:
        return

    if check.policy == FailurePolicy.RETRY:
        raise OutputGuardrailRetryable(
            check.message or f"Output guardrail {check.name} requires retry",
            guardrail_name=check.name,
            metadata=check.metadata,
        )

    if check.policy == FailurePolicy.EXCEPTION:
        raise GuardrailBlocked(
            check.message or f"Output blocked by {check.name}",
            phase="output",
            guardrail_name=check.name,
        )
