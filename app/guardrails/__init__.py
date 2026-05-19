"""Guardrails multicapa (defense-in-depth) para el estimador."""

from app.guardrails.config import GUARDRAILS_VERSION
from app.guardrails.exceptions import (
    GuardrailBlocked,
    InputGuardrailViolation,
    ModerationUnavailable,
    OutputGuardrailRetryable,
)
from app.guardrails.input import check_input, run_input_guardrails
from app.guardrails.output import enforce_scope_response_public, run_output_guardrails
from app.guardrails.pipeline import create_openai_client, validate_rendered_prompts
from app.guardrails.types import InputGuardrailResult

__all__ = [
    "GUARDRAILS_VERSION",
    "GuardrailBlocked",
    "InputGuardrailResult",
    "InputGuardrailViolation",
    "ModerationUnavailable",
    "OutputGuardrailRetryable",
    "check_input",
    "create_openai_client",
    "enforce_scope_response_public",
    "run_input_guardrails",
    "run_output_guardrails",
    "validate_rendered_prompts",
]
