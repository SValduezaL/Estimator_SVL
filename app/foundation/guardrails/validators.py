"""Validadores semánticos de EstimationResult (post-schema)."""

from __future__ import annotations

from app.config import Settings
from app.guardrails.pii import check_pii, redact_pii
from app.guardrails.types import FailurePolicy
from app.guardrails.types import GuardrailCheckResult
from app.schemas.estimation_common import LOW_CONFIDENCE_THRESHOLD, OUT_OF_SCOPE_PREFIX
from app.schemas.estimation_output import EstimationResult


def validate_cost_coherence(result: EstimationResult, *, settings: Settings) -> GuardrailCheckResult:
    name = "cost_coherence"
    min_rate = settings.guardrails_min_eur_per_hour
    max_rate = settings.guardrails_max_eur_per_hour
    violations: list[str] = []
    for phase in result.phases:
        if phase.hours <= 0:
            continue
        rate = phase.cost_eur / phase.hours
        if rate < min_rate or rate > max_rate:
            violations.append(f"{phase.name}:{rate:.0f}eur/h")
    if violations:
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=FailurePolicy.RETRY,
            message=f"Implicit EUR/h out of range: {', '.join(violations[:3])}",
            metadata={"violations": violations},
        )
    return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)


def validate_temporal_coherence(result: EstimationResult, *, settings: Settings) -> GuardrailCheckResult:
    name = "temporal_coherence"
    total_hours = sum(p.hours for p in result.phases)
    hpw = settings.guardrails_hours_per_week
    min_weeks = max(1, total_hours // (hpw * 8) if total_hours else 1)
    max_weeks = max(1, (total_hours + hpw - 1) // hpw) if total_hours else 104
    if result.total_duration_weeks < min_weeks // 2 or result.total_duration_weeks > max_weeks * 4:
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=FailurePolicy.RETRY,
            message=(
                f"total_duration_weeks={result.total_duration_weeks} inconsistent "
                f"with sum(hours)={total_hours}"
            ),
            metadata={"total_hours": total_hours, "min_weeks": min_weeks, "max_weeks": max_weeks},
        )
    return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)


def validate_confidence_consistency(result: EstimationResult) -> GuardrailCheckResult:
    name = "confidence_consistency"
    if result.confidence_pct >= LOW_CONFIDENCE_THRESHOLD and result.summary.startswith(
        OUT_OF_SCOPE_PREFIX
    ):
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=FailurePolicy.FILTER,
            message="High confidence with out-of-scope prefix",
        )
    phase_confidences = [p.confidence_pct for p in result.phases if p.confidence_pct is not None]
    if phase_confidences:
        avg = sum(phase_confidences) / len(phase_confidences)
        if abs(avg - result.confidence_pct) > 50:
            return GuardrailCheckResult(
                name=name,
                passed=False,
                policy=FailurePolicy.LOG_ONLY,
                message="Global confidence diverges from phase averages",
                metadata={"avg_phase_confidence": avg},
            )
    return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)


def validate_non_empty_response(result: EstimationResult) -> GuardrailCheckResult:
    name = "non_empty_response"
    if not result.summary.strip():
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=FailurePolicy.RETRY,
            message="Empty summary",
        )
    for phase in result.phases:
        if len(phase.deliverable.strip()) < 5:
            return GuardrailCheckResult(
                name=name,
                passed=False,
                policy=FailurePolicy.RETRY,
                message=f"Phase {phase.name!r} has trivial deliverable",
            )
    return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)


def validate_phase_sanity(result: EstimationResult) -> GuardrailCheckResult:
    name = "phase_sanity"
    names = [p.name.lower().strip() for p in result.phases]
    if len(names) != len(set(names)):
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=FailurePolicy.RETRY,
            message="Duplicate phase names",
        )
    if any(p.hours > 2000 or p.cost_eur > 500_000 for p in result.phases):
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=FailurePolicy.EXCEPTION,
            message="Absurd phase hours or cost",
        )
    return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)


def validate_output_pii(result: EstimationResult, *, settings: Settings) -> GuardrailCheckResult:
    combined = f"{result.summary}\n{result.reasoning}"
    check = check_pii(combined, settings=settings, input_mode=False, log_only=False)
    if check.passed:
        return check
    redacted_summary = redact_pii(result.summary)
    redacted_reasoning = redact_pii(result.reasoning)
    return GuardrailCheckResult(
        name=check.name,
        passed=False,
        policy=FailurePolicy.FILTER,
        message=check.message,
        metadata=check.metadata,
        filtered_text=f"{redacted_summary}\n---\n{redacted_reasoning}",
    )


def run_semantic_validators(
    result: EstimationResult,
    *,
    settings: Settings,
) -> list[GuardrailCheckResult]:
    if not settings.guardrails_output_semantic_enabled:
        return []
    return [
        validate_non_empty_response(result),
        validate_cost_coherence(result, settings=settings),
        validate_temporal_coherence(result, settings=settings),
        validate_confidence_consistency(result),
        validate_phase_sanity(result),
        validate_output_pii(result, settings=settings),
    ]
