"""Validación post-render de prompts."""

from __future__ import annotations

import structlog

from app.config import Settings
from app.foundation.guardrails.types import FailurePolicy
from app.foundation.guardrails.types import GuardrailCheckResult

log = structlog.get_logger(__name__)


def validate_rendered_prompts(
    *,
    system_prompt: str,
    user_message: str,
    settings: Settings,
) -> GuardrailCheckResult:
    """Comprueba delimitadores y tamaño tras render Jinja."""
    name = "prompt_render"
    total_len = len(system_prompt) + len(user_message)
    if total_len > settings.guardrails_prompt_max_chars:
        log.warning(
            "prompt_render_oversized",
            log_category="guardrails",
            total_chars=total_len,
            max_chars=settings.guardrails_prompt_max_chars,
        )
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=FailurePolicy.EXCEPTION,
            message="Rendered prompt exceeds maximum size",
            metadata={"total_chars": total_len},
        )

    if "<user_request>" not in user_message and "<project_description>" not in user_message:
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=FailurePolicy.LOG_ONLY,
            message="User message missing expected XML delimiters",
        )

    if user_message.count("<") != user_message.count(">"):
        log.info(
            "prompt_xml_imbalance",
            log_category="guardrails",
            open_count=user_message.count("<"),
            close_count=user_message.count(">"),
        )

    return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)
