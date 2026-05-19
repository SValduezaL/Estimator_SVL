"""Orquestador de guardrails de salida."""

from __future__ import annotations

import hashlib

from app.config import Settings
from app.guardrails.exceptions import GuardrailBlocked
from app.guardrails.filters import (
    build_safe_fallback,
    degrade_low_confidence,
    enforce_scope_response,
)
from app.guardrails.judge import JudgeContext, run_output_judges
from app.guardrails.pii import redact_pii
from app.guardrails.policies import apply_output_policy
from app.guardrails.types import FailurePolicy
from app.guardrails.telemetry import log_guardrail_event, log_policy_applied
from app.guardrails.types import GuardrailCheckResult, OutputGuardrailContext
from app.guardrails.validators import run_semantic_validators
from app.schemas.estimation_common import DetailLevel, ProjectType
from app.schemas.estimation_output import EstimationResult


def _apply_filter(check: GuardrailCheckResult, current: EstimationResult) -> EstimationResult:
    if check.name == "pii_output" and check.filtered_text:
        parts = check.filtered_text.split("\n---\n", 1)
        return current.model_copy(
            update={
                "summary": parts[0][:1200],
                "reasoning": parts[1] if len(parts) > 1 else redact_pii(current.reasoning),
            }
        )
    if check.name == "confidence_consistency":
        return enforce_scope_response(current)
    return current


def run_output_guardrails(
    result: EstimationResult,
    *,
    settings: Settings,
    detail_level: DetailLevel,
    project_type: ProjectType,
    description: str = "",
) -> EstimationResult:
    """Validación semántica, filtros y judge hooks sobre salida del LLM."""
    if not settings.guardrails_enabled:
        return result

    _ = OutputGuardrailContext(
        detail_level=detail_level.value,
        project_type=project_type.value,
    )

    current = result

    for check in run_semantic_validators(current, settings=settings):
        log_policy_applied(
            guardrail_name=check.name,
            policy=check.policy,
            passed=check.passed,
        )
        if check.passed:
            continue

        if check.policy == FailurePolicy.FILTER:
            current = _apply_filter(check, current)
            if check.name == "pii_output":
                log_guardrail_event("output_pii_redacted")
            continue

        if check.policy in (FailurePolicy.RETRY, FailurePolicy.EXCEPTION):
            try:
                apply_output_policy(check)
            except GuardrailBlocked:
                current = build_safe_fallback(
                    project_type=project_type,
                    detail_level=detail_level,
                    reason=check.name,
                )
                break

    desc_hash = hashlib.sha256(description.encode("utf-8")).hexdigest() if description else ""
    verdict = run_output_judges(
        JudgeContext(
            description_hash=desc_hash,
            project_type=project_type.value,
            detail_level=detail_level.value,
            result=current,
        ),
        enabled=settings.guardrails_judge_enabled,
    )
    if not verdict.passed:
        log_guardrail_event("output_judge_failed", message=verdict.message)
        current = build_safe_fallback(
            project_type=project_type,
            detail_level=detail_level,
            reason="judge",
        )

    current = enforce_scope_response(current)
    current = degrade_low_confidence(current)
    return current


def enforce_scope_response_public(result: EstimationResult) -> EstimationResult:
    """Re-export del filtro de alcance (compatibilidad baseline)."""
    return enforce_scope_response(result)
