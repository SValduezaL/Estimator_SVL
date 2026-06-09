"""Tests del pipeline de entrada."""

from app.foundation.guardrails.input import run_input_guardrails
from tests.foundation.guardrails.conftest import guardrails_disabled_settings, guardrails_strict_settings


def test_disabled_returns_same_text(guardrails_disabled_settings) -> None:
    text = "A" * 25
    out = run_input_guardrails(text, settings=guardrails_disabled_settings)
    assert out.text == text


def test_clean_text_passes(guardrails_strict_settings) -> None:
    text = (
        "We need a B2B SaaS billing MVP with multi-tenant auth and Stripe webhooks "
        "for our startup."
    )
    out = run_input_guardrails(
        text,
        settings=guardrails_strict_settings,
        openai_client=None,
    )
    assert out.text == text
