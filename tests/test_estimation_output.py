"""Tests de ``EstimationResult`` y validación de ``reasoning``."""

import pytest

from app.schemas.estimation_common import OUT_OF_SCOPE_PREFIX
from app.schemas.estimation_output import EstimationResult, Phase
from app.services.structured_llm import ReasoningLengthError, assert_reasoning_length
from app.schemas.estimation_common import DetailLevel

_VALID = EstimationResult(
    summary="MVP SaaS de facturación recurrente multi-tenant con pasarela y panel admin.",
    confidence_pct=72,
    phases=[
        Phase(
            name="Fundaciones",
            deliverable="Auth, RBAC y modelo tenant",
            hours=24,
            cost_eur=1440,
        ),
        Phase(
            name="Cobros",
            deliverable="Pasarela y webhooks idempotentes",
            hours=30,
            cost_eur=1800,
        ),
        Phase(
            name="Producto",
            deliverable="API versionada y panel React",
            hours=38,
            cost_eur=2280,
        ),
    ],
    total_duration_weeks=7,
    total_cost_eur=5520,
    reasoning=(
        "## Por qué tres fases\n"
        "Separé fundaciones, cobros y producto para aislar el riesgo de webhooks antes del UI.\n\n"
        "**Stack:** FastAPI + PostgreSQL + React por madurez del equipo y time-to-market.\n\n"
        "El plazo de **7 semanas** asume un full-stack senior y un frontend mid en paralelo."
    ),
)


def test_valid_estimation_passes_validators() -> None:
    assert _VALID.total_cost_eur == sum(p.cost_eur for p in _VALID.phases)


def test_phases_sum_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="phases sum"):
        EstimationResult(
            summary="x" * 10,
            confidence_pct=80,
            phases=[
                Phase(
                    name="Fase A",
                    deliverable="Entrega A",
                    hours=10,
                    cost_eur=1000,
                )
            ],
            total_duration_weeks=2,
            total_cost_eur=999,
            reasoning="## Justificación\n" + ("texto " * 40),
        )


def test_low_confidence_requires_prefix() -> None:
    with pytest.raises(ValueError, match=OUT_OF_SCOPE_PREFIX):
        EstimationResult(
            summary="Descripción sin prefijo obligatorio.",
            confidence_pct=30,
            phases=[
                Phase(
                    name="Fase A",
                    deliverable="Entrega A",
                    hours=10,
                    cost_eur=1000,
                )
            ],
            total_duration_weeks=2,
            total_cost_eur=1000,
            reasoning="## Justificación\n" + ("texto " * 40),
        )


def test_assert_reasoning_length_medium_ok() -> None:
    assert_reasoning_length(_VALID, DetailLevel.MEDIUM)


def test_assert_reasoning_length_too_short() -> None:
    short = _VALID.model_copy(update={"reasoning": "## Corto\n" + ("x" * 50)})
    with pytest.raises(ReasoningLengthError):
        assert_reasoning_length(short, DetailLevel.MEDIUM)
