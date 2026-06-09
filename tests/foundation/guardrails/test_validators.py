"""Tests de validadores semánticos de salida."""

from app.foundation.guardrails.validators import (
    validate_confidence_consistency,
    validate_cost_coherence,
    validate_non_empty_response,
    validate_phase_sanity,
)
from app.domain.schemas.estimation_output import EstimationResult, Phase
from tests.foundation.guardrails.conftest import guardrails_strict_settings
from tests.conftest import _STUB_RESULT


def test_valid_stub_passes_coherence(guardrails_strict_settings) -> None:
    check = validate_cost_coherence(_STUB_RESULT, settings=guardrails_strict_settings)
    assert check.passed


def test_duplicate_phases_retry() -> None:
    phase = Phase(
        name="Fase A",
        deliverable="Entrega duplicada aquí",
        stack=["Python"],
        hours=10,
        cost_eur=1000,
    )
    result = EstimationResult(
        summary="x" * 20,
        confidence_pct=80,
        phases=[phase, phase.model_copy()],
        total_duration_weeks=2,
        total_cost_eur=2000,
        reasoning="## División\nDos fases iguales por error.",
    )
    check = validate_phase_sanity(result)
    assert not check.passed


def test_high_confidence_with_oos_prefix_filters() -> None:
    result = _STUB_RESULT.model_copy(
        update={
            "confidence_pct": 90,
            "summary": "[FUERA_DE_ALCANCE] test " + "x" * 10,
        }
    )
    check = validate_confidence_consistency(result)
    assert not check.passed


def test_empty_summary_fails() -> None:
    result = _STUB_RESULT.model_copy(update={"summary": " " * 15})
    check = validate_non_empty_response(result)
    assert not check.passed
