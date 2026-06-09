"""Tests de detección PII."""

import pytest

from app.foundation.guardrails.exceptions import InputGuardrailViolation
from app.foundation.guardrails.input import run_input_guardrails
from app.foundation.guardrails.pii import check_pii, redact_pii
from tests.foundation.guardrails.conftest import guardrails_strict_settings


def test_email_detected(guardrails_strict_settings) -> None:
    check = check_pii(
        "Contact us at user@example.com for details " + "x" * 10,
        settings=guardrails_strict_settings,
        input_mode=True,
    )
    assert not check.passed


def test_redact_pii() -> None:
    out = redact_pii("Email: user@example.com")
    assert "[REDACTED_PII]" in out
    assert "@" not in out


def test_run_input_raises_on_email(guardrails_strict_settings) -> None:
    with pytest.raises(InputGuardrailViolation) as exc:
        run_input_guardrails(
            "Build an app. Reach me at user@example.com please.",
            settings=guardrails_strict_settings,
            openai_client=None,
        )
    assert exc.value.reason == "pii"
