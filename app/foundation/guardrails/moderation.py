"""OpenAI Moderation API."""

from __future__ import annotations

from typing import Any

import structlog

from app.config import Settings
from app.guardrails.exceptions import ModerationUnavailable
from app.guardrails.types import FailurePolicy
from app.guardrails.telemetry import guardrail_timer, log_guardrail_event
from app.guardrails.types import GuardrailCheckResult, ModerationScores

log = structlog.get_logger(__name__)


def _extract_flagged_categories(result: Any) -> list[str]:
    categories = getattr(result, "categories", None)
    if categories is None:
        return []
    data = (
        categories.model_dump() if hasattr(categories, "model_dump") else categories.__dict__
    )
    return [name for name, flagged in data.items() if flagged]


def _extract_category_scores(result: Any) -> dict[str, float]:
    scores = getattr(result, "category_scores", None)
    if scores is None:
        return {}
    data = scores.model_dump() if hasattr(scores, "model_dump") else scores.__dict__
    return {str(k): float(v) for k, v in data.items()}


def _exceeds_thresholds(
    category_scores: dict[str, float],
    thresholds: dict[str, float],
) -> list[str]:
    if not thresholds:
        return []
    exceeded: list[str] = []
    for cat, threshold in thresholds.items():
        score = category_scores.get(cat)
        if score is not None and score >= threshold:
            exceeded.append(cat)
    return exceeded


def check_moderation(
    text: str,
    *,
    settings: Settings,
    openai_client: Any | None,
) -> GuardrailCheckResult:
    """Llama a OpenAI Moderation API."""
    name = "moderation"
    if not settings.guardrails_moderation_enabled:
        return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)

    policy = (
        FailurePolicy.LOG_ONLY
        if settings.guardrails_moderation_log_only
        else FailurePolicy.EXCEPTION
    )

    if openai_client is None:
        return GuardrailCheckResult(name=name, passed=True, policy=policy)

    with guardrail_timer(name):
        try:
            response = openai_client.moderations.create(
                input=text,
                model=settings.guardrails_moderation_model,
            )
        except Exception as exc:
            log.warning(
                "moderation_call_failed",
                log_category="guardrails",
                error_type=type(exc).__name__,
                error_message=str(exc),
                error_recoverable=settings.guardrails_fail_open_on_moderation_error,
            )
            if settings.guardrails_fail_open_on_moderation_error:
                return GuardrailCheckResult(
                    name=name,
                    passed=True,
                    policy=policy,
                    metadata={"moderation_unavailable": True},
                )
            raise ModerationUnavailable(str(exc)) from exc

        result = response.results[0]
        flagged = bool(getattr(result, "flagged", False))
        categories = _extract_flagged_categories(result)
        category_scores = _extract_category_scores(result)
        threshold_hits = _exceeds_thresholds(
            category_scores, settings.guardrails_moderation_thresholds
        )

        scores = ModerationScores(
            flagged=flagged,
            categories=categories,
            category_scores=category_scores,
        )

        log_guardrail_event(
            "moderation_scores_recorded",
            flagged=flagged,
            categories=categories,
            category_scores=category_scores,
        )

        violated = flagged or bool(threshold_hits)
        if not violated:
            return GuardrailCheckResult(
                name=name,
                passed=True,
                policy=policy,
                metadata={"scores": category_scores},
            )

        log_guardrail_event(
            "moderation_flagged",
            categories=categories or threshold_hits,
            category_scores=category_scores,
        )

        cats = categories or threshold_hits
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=policy,
            message=f"Input flagged by moderation: {', '.join(cats) or 'unspecified'}",
            metadata={
                "categories": cats,
                "category_scores": category_scores,
                "scores": scores,
            },
        )
