"""Orquestador de guardrails de entrada."""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.foundation.guardrails.exceptions import InputGuardrailViolation, ModerationUnavailable
from app.foundation.guardrails.injection import check_prompt_injection
from app.foundation.guardrails.moderation import check_moderation
from app.foundation.guardrails.pii import check_pii
from app.foundation.guardrails.policies import apply_input_policy
from app.foundation.guardrails.types import FailurePolicy
from app.foundation.guardrails.telemetry import log_guardrail_event, log_policy_applied
from app.foundation.guardrails.types import GuardrailCheckResult, InputGuardrailResult, InputViolationReason

_REASON_MAP: dict[str, InputViolationReason] = {
    "moderation": "moderation",
    "prompt_injection": "prompt_injection",
    "pii_input": "pii",
}


def run_input_guardrails(
    text: str,
    *,
    settings: Settings,
    openai_client: Any | None = None,
) -> InputGuardrailResult:
    """Moderation → injection → PII. Devuelve texto posiblemente redactado."""
    if not settings.guardrails_enabled:
        return InputGuardrailResult(text=text)

    checks: list[GuardrailCheckResult] = []
    current = text

    layers: list[tuple[str, GuardrailCheckResult]] = []

    mod = check_moderation(current, settings=settings, openai_client=openai_client)
    layers.append(("moderation", mod))
    inj = check_prompt_injection(current, settings=settings)
    layers.append(("prompt_injection", inj))
    pii = check_pii(current, settings=settings, input_mode=True)
    layers.append(("pii", pii))

    for reason_key, check in layers:
        checks.append(check)
        log_policy_applied(
            guardrail_name=check.name,
            policy=check.policy,
            passed=check.passed,
        )
        if check.passed:
            continue

        reason = _REASON_MAP.get(check.name, "pii")
        if check.policy == FailurePolicy.FILTER and check.filtered_text:
            current = check.filtered_text
            log_guardrail_event("guardrail_input_filtered", guardrail_name=check.name)
            continue

        try:
            apply_input_policy(check, text=current, reason=reason)
        except InputGuardrailViolation:
            raise
        except ModerationUnavailable:
            raise InputGuardrailViolation(
                "Moderation service unavailable",
                reason="moderation",
            ) from None

    return InputGuardrailResult(text=current, checks=checks)


def check_input(description: str, *, openai_client: Any | None = None) -> None:
    """API legacy del baseline: usa Settings por defecto del proceso."""
    from app.config import get_settings

    result = run_input_guardrails(
        description,
        settings=get_settings(),
        openai_client=openai_client,
    )
    _ = result
