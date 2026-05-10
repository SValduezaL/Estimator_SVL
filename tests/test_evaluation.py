"""Tests unitarios del evaluador de Markdown (sin depender de CANONICAL_EXAMPLES)."""

import pytest

from app.services.evaluation import (
    COMPLETE_FINISH_REASONS,
    evaluate_estimation_structure,
)

# Markdown mínimo válido para el evaluador (tabla + totales alineados con la fila).
_SYNTHETIC_VALID_ESTIMATION_MARKDOWN = """\
## Proyecto sintético de prueba

### Desglose de tareas

| Tarea | Horas | Coste (EUR) |
|------|------:|------------|
| Implementación inicial | 10 | 1.000 |

### Totales

- **Total de horas:** 10
- **Coste total:** 1.000 EUR

### Equipo recomendado

- 1 desarrollador/a

### Duración estimada

**2 semanas** en solitario.
"""


def test_well_formed_synthetic_markdown_passes_all_checks() -> None:
    result = evaluate_estimation_structure(
        _SYNTHETIC_VALID_ESTIMATION_MARKDOWN,
        finish_reason="stop",
    )
    assert result.has_title
    assert result.has_breakdown_table
    assert result.has_totals_section
    assert result.has_team_section
    assert result.has_duration_section
    assert result.declared_total_hours == 10
    assert result.sum_row_hours == 10
    assert result.hours_match is True
    assert result.declared_total_cost == 1000
    assert result.sum_row_cost == 1000
    assert result.cost_match is True
    assert result.finish_reason_ok is True
    assert result.score == 1.0
    assert result.issues == []


@pytest.mark.parametrize("finish_reason", sorted(COMPLETE_FINISH_REASONS))
def test_openai_stop_anthropic_end_turn_and_stop_sequence_finish_complete(
    finish_reason: str,
) -> None:
    """Valores en COMPLETE_FINISH_REASONS = finalización completa según OpenAI/Anthropic → OK."""
    result = evaluate_estimation_structure(
        _SYNTHETIC_VALID_ESTIMATION_MARKDOWN,
        finish_reason=finish_reason,
    )
    assert result.finish_reason_ok is True
    assert result.score == 1.0
    assert result.issues == []


def test_finish_reason_not_in_complete_set_is_not_ok() -> None:
    """Cualquier otro valor (p. ej. string arbitrario) no cuenta como respuesta completa."""
    result = evaluate_estimation_structure(
        _SYNTHETIC_VALID_ESTIMATION_MARKDOWN,
        finish_reason="model_terminated_unknown",
    )
    assert result.finish_reason_ok is False
    assert result.score < 1.0


@pytest.mark.parametrize(
    "finish_reason",
    [
        "length",  # OpenAI: truncado por max_tokens
        "max_tokens",  # Anthropic: mismo concepto
        "content_filter",  # OpenAI: filtrado
        "tool_calls",  # OpenAI: fin por herramientas (no es respuesta final de texto)
    ],
)
def test_truncation_filter_and_tool_stop_yield_finish_reason_not_ok(finish_reason: str) -> None:
    result = evaluate_estimation_structure(
        _SYNTHETIC_VALID_ESTIMATION_MARKDOWN,
        finish_reason=finish_reason,
    )
    assert result.finish_reason_ok is False
    assert any("truncated" in msg.lower() or "finish_reason" in msg for msg in result.issues)
    assert result.score < 1.0


def test_mismatched_total_hours_is_flagged() -> None:
    text = _SYNTHETIC_VALID_ESTIMATION_MARKDOWN.replace(
        "**Total de horas:** 10",
        "**Total de horas:** 999",
    )
    result = evaluate_estimation_structure(text, finish_reason="stop")
    assert result.hours_match is False
    assert any("Total hours mismatch" in msg for msg in result.issues)
    assert result.score < 1.0


def test_missing_table_is_detected() -> None:
    text = "## Just a title\n\nNo table here, just prose."
    result = evaluate_estimation_structure(text, finish_reason="stop")
    assert result.has_title is True
    assert result.has_breakdown_table is False
    assert any("breakdown table" in msg for msg in result.issues)
    assert result.sum_row_hours is None


def test_empty_text_scores_zero_and_lists_all_issues() -> None:
    result = evaluate_estimation_structure("", finish_reason="stop")
    assert result.score < 0.5
    assert result.has_title is False
    assert result.has_breakdown_table is False
