"""Tests de ``EstimationResult`` y validación de ``reasoning``."""

import pytest

from app.domain.schemas.estimation_common import OUT_OF_SCOPE_PREFIX
from app.domain.schemas.estimation_output import EstimationResult, Phase
from app.foundation.llm.structured import ReasoningLengthError, assert_reasoning_length
from app.domain.schemas.estimation_common import DetailLevel

_VALID = EstimationResult(
    summary="MVP SaaS de facturación recurrente multi-tenant con pasarela y panel admin.",
    confidence_pct=72,
    phases=[
        Phase(
            name="Fundaciones",
            deliverable="Auth, RBAC y modelo tenant",
            stack=["FastAPI", "PostgreSQL"],
            hours=24,
            cost_eur=1440,
        ),
        Phase(
            name="Cobros",
            deliverable="Pasarela y webhooks idempotentes",
            stack=["Stripe API", "Redis"],
            hours=30,
            cost_eur=1800,
        ),
        Phase(
            name="Producto",
            deliverable="API versionada y panel React",
            stack=["React", "OpenAPI"],
            hours=38,
            cost_eur=2280,
        ),
    ],
    total_duration_weeks=7,
    total_cost_eur=5520,
    reasoning=(
        "## División en fases\n"
        "Separé fundaciones, cobros y producto para aislar el riesgo de webhooks antes del UI.\n\n"
        "## Stack por fase\n"
        "Fundaciones debe cerrar identidad antes de exponer cobros; cobros concentra integración; "
        "producto consume contratos ya estables.\n\n"
        "## Esfuerzo por fase\n"
        "Cobros lleva más horas por idempotencia; fundaciones son bloqueantes pero acotadas; "
        "producto incluye iteración de onboarding."
    ),
)


def test_valid_estimation_passes_validators() -> None:
    assert _VALID.total_cost_eur == sum(p.cost_eur for p in _VALID.phases)
    assert all(p.stack for p in _VALID.phases)


def test_phase_requires_non_empty_stack() -> None:
    with pytest.raises(ValueError):
        Phase(
            name="Fase A",
            deliverable="Entrega A",
            stack=[],
            hours=10,
            cost_eur=1000,
        )


def test_phases_sum_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="phases sum"):
        EstimationResult(
            summary="x" * 10,
            confidence_pct=80,
            phases=[
                Phase(
                    name="Fase A",
                    deliverable="Entrega A",
                    stack=["Python"],
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
                    stack=["Python"],
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


def test_assert_reasoning_length_truncates_when_too_long() -> None:
    long_reasoning = "## Título\n\n" + ("párrafo de justificación. " * 80)
    long = _VALID.model_copy(update={"reasoning": long_reasoning})
    out = assert_reasoning_length(long, DetailLevel.MEDIUM)
    assert len(out.reasoning) <= 1400
    assert len(out.reasoning) >= 200
