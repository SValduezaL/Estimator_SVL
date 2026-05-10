import json

import pytest

from app.context.examples import (
    CANONICAL_EXAMPLES,
    CanonicalExample,
    format_examples_for_prompt,
    select_examples,
)
from app.services.evaluation import COMPLETE_FINISH_REASONS, evaluate_estimation_structure


def test_format_markdown_contains_table_header() -> None:
    out = format_examples_for_prompt(select_examples(2), fmt="markdown")
    assert "--- EJEMPLO 1 ---" in out
    assert "--- EJEMPLO 2 ---" in out
    assert "| Tarea | Horas | Coste (EUR) |" in out


def test_format_json_is_valid_json() -> None:
    want = min(3, len(CANONICAL_EXAMPLES))
    out = format_examples_for_prompt(select_examples(3), fmt="json")
    assert out.startswith("Ejemplos de referencia (JSON):")
    payload = json.loads(out.split("Ejemplos de referencia (JSON):", 1)[1])
    assert isinstance(payload, list) and len(payload) == want
    first = payload[0]
    assert {"meeting_summary", "title", "breakdown", "totals", "team", "duration_weeks"} <= set(
        first.keys()
    )
    assert first["totals"]["hours"] == CANONICAL_EXAMPLES[0].total_hours
    assert first["totals"]["cost_eur"] == CANONICAL_EXAMPLES[0].total_cost


def test_format_narrative_mentions_hours_and_weeks() -> None:
    out = format_examples_for_prompt(select_examples(1), fmt="narrative")
    ex = CANONICAL_EXAMPLES[0]
    assert f"{ex.total_hours} horas" in out
    assert f"{ex.duration_weeks} semanas" in out
    assert ex.title in out


def test_select_examples_zero_returns_empty() -> None:
    assert select_examples(0) == []
    assert format_examples_for_prompt([], fmt="markdown") == ""
    assert format_examples_for_prompt([], fmt="json") == ""
    assert format_examples_for_prompt([], fmt="narrative") == ""


def test_select_examples_caps_at_available() -> None:
    assert len(select_examples(99)) == len(CANONICAL_EXAMPLES)


def test_select_examples_negative_returns_empty() -> None:
    assert select_examples(-1) == []


def test_canonical_examples_have_calibrated_totals() -> None:
    for ex in CANONICAL_EXAMPLES:
        sum_h = sum(h for _, h, _ in ex.breakdown)
        sum_c = sum(c for _, _, c in ex.breakdown)
        assert sum_h == ex.total_hours, ex.title
        assert sum_c == ex.total_cost, ex.title


@pytest.mark.parametrize("ex", CANONICAL_EXAMPLES, ids=[ex.title for ex in CANONICAL_EXAMPLES])
@pytest.mark.parametrize("finish_reason", sorted(COMPLETE_FINISH_REASONS))
def test_canonical_estimation_passes_structure_evaluation_when_finish_is_complete(
    ex: CanonicalExample,
    finish_reason: str,
) -> None:
    """Contrato ejemplos ↔ evaluador: cada Markdown canónico es válido con todo finish_reason completo."""
    result = evaluate_estimation_structure(ex.estimation_markdown, finish_reason=finish_reason)
    assert result.score == 1.0, (ex.title, finish_reason, result.issues)
    assert result.issues == []
    assert result.declared_total_hours == ex.total_hours
    assert result.sum_row_hours == ex.total_hours
    assert result.declared_total_cost == ex.total_cost
    assert result.sum_row_cost == ex.total_cost
    assert result.finish_reason_ok is True


def test_format_unknown_raises() -> None:
    with pytest.raises(ValueError):
        format_examples_for_prompt(select_examples(1), fmt="yaml")  # type: ignore[arg-type]
