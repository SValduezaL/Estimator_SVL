"""Tests deterministas de plantillas Jinja2 (sin llamadas al LLM)."""

from __future__ import annotations

import pytest
from jinja2 import TemplateNotFound, UndefinedError

from app.prompts.loader import build_estimation_jinja_environment, render_estimation_prompt
from app.schemas.estimation import DetailLevel, EstimationRequest, OutputFormat, ProjectType


def _make_request(**overrides: object) -> EstimationRequest:
    base = {
        "description": "Descripción mínima válida para tests de plantillas.",
        "project_type": ProjectType.WEB_SAAS,
        "detail_level": DetailLevel.MEDIUM,
        "output_format": OutputFormat.LINE_ITEMS,
    }
    base.update(overrides)
    return EstimationRequest(**base)


def test_user_prompt_has_xml_project_description() -> None:
    _system, user = render_estimation_prompt(_make_request())
    assert "<project_description>" in user
    assert "</project_description>" in user
    assert "Descripción mínima válida" in user


def test_detailed_adds_confidence_pct_instruction() -> None:
    system_detailed, _ = render_estimation_prompt(_make_request(detail_level=DetailLevel.DETAILED))
    system_summary, _ = render_estimation_prompt(_make_request(detail_level=DetailLevel.SUMMARY))
    assert "confidence_pct" in system_detailed
    assert "confidence_pct" not in system_summary


def test_phases_table_activates_phase_columns() -> None:
    system, _ = render_estimation_prompt(_make_request(output_format=OutputFormat.PHASES_TABLE))
    assert "| Fase | Entregable principal | Horas (rango) | Riesgos / notas |" in system


def test_line_items_activates_task_table_columns() -> None:
    system, _ = render_estimation_prompt(_make_request(output_format=OutputFormat.LINE_ITEMS))
    assert "| Tarea | Horas | Coste (EUR) |" in system


def test_narrative_branch_differs_from_phases() -> None:
    sys_narr, _ = render_estimation_prompt(_make_request(output_format=OutputFormat.NARRATIVE))
    sys_phases, _ = render_estimation_prompt(_make_request(output_format=OutputFormat.PHASES_TABLE))
    assert "narrativo" in sys_narr.lower()
    assert sys_narr != sys_phases


def test_examples_j2_content_is_in_system_prompt() -> None:
    system, _ = render_estimation_prompt(_make_request())
    assert "<few_shot_selected" in system
    assert "<few_shot_policy>" in system
    assert system.count("<reference_estimation") == 3
    assert "webhooks idempotentes" in system.lower()


def test_few_shots_follow_project_type_not_mixed_domains() -> None:
    sm, _ = render_estimation_prompt(_make_request(project_type=ProjectType.MOBILE_APP))
    sw, _ = render_estimation_prompt(_make_request(project_type=ProjectType.WEB_SAAS))
    sd, _ = render_estimation_prompt(_make_request(project_type=ProjectType.DATA_PIPELINE))
    assert "inventario en tienda" in sm.lower() or "cadena retail" in sm.lower()
    assert "webhooks idempotentes" in sw.lower()
    assert "cdc" in sd.lower() or "linaje" in sd.lower()
    assert "cadena retail" not in sw.lower()


def test_summary_format_combo_changes_few_shot_body() -> None:
    sp, _ = render_estimation_prompt(
        _make_request(detail_level=DetailLevel.SUMMARY, output_format=OutputFormat.PHASES_TABLE)
    )
    sl, _ = render_estimation_prompt(
        _make_request(detail_level=DetailLevel.SUMMARY, output_format=OutputFormat.LINE_ITEMS)
    )
    assert "108–132" in sp
    assert "| 28 | 1.680 |" in sl


def test_project_type_conditional_changes_system() -> None:
    s_mobile, _ = render_estimation_prompt(_make_request(project_type=ProjectType.MOBILE_APP))
    s_pipe, _ = render_estimation_prompt(_make_request(project_type=ProjectType.DATA_PIPELINE))
    assert "iOS/Android" in s_mobile
    assert "SLAs de frescura" in s_pipe


def test_strictundefined_errors_on_unknown_variable() -> None:
    env = build_estimation_jinja_environment()
    tmpl = env.from_string("{{ variable_inexistente }}")
    with pytest.raises(UndefinedError):
        tmpl.render()


def test_unknown_version_raises_template_not_found() -> None:
    with pytest.raises(TemplateNotFound):
        render_estimation_prompt(_make_request(), version="v999_nonexistent")
