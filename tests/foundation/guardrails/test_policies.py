"""Tests de políticas de fallo."""

import pytest

from app.foundation.guardrails.exceptions import InputGuardrailViolation, OutputGuardrailRetryable
from app.foundation.guardrails.policies import apply_input_policy, apply_output_policy
from app.foundation.guardrails.types import FailurePolicy
from app.foundation.guardrails.types import GuardrailCheckResult


def test_apply_input_exception() -> None:
    check = GuardrailCheckResult(
        name="prompt_injection",
        passed=False,
        policy=FailurePolicy.EXCEPTION,
        message="blocked",
    )
    with pytest.raises(InputGuardrailViolation) as exc:
        apply_input_policy(check, text="x", reason="prompt_injection")
    assert exc.value.reason == "prompt_injection"


def test_apply_input_log_only_returns_text() -> None:
    check = GuardrailCheckResult(
        name="pii_input",
        passed=False,
        policy=FailurePolicy.LOG_ONLY,
        filtered_text="redacted",
    )
    assert apply_input_policy(check, text="original", reason="pii") == "original"


def test_apply_output_retry() -> None:
    check = GuardrailCheckResult(
        name="cost_coherence",
        passed=False,
        policy=FailurePolicy.RETRY,
        message="retry",
    )
    with pytest.raises(OutputGuardrailRetryable):
        apply_output_policy(check)
