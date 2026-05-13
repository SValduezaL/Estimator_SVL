"""Tests deterministas de plantillas Jinja2 (sin llamadas al LLM)."""

from __future__ import annotations

import pytest
from jinja2 import TemplateNotFound, UndefinedError

from app.prompts.loader import build_estimation_jinja_environment, render_estimation_prompt
from app.prompts.registry import (
    DEFAULT_ESTIMATION_BUNDLE,
    ESTIMATION_BUNDLE_V1,
    ESTIMATION_PROMPT_VERSION,
    get_estimation_bundle,
)
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


_PHASES_TABLE_KEYWORD = (
    "| Fase | Entregable principal | Horas (rango) | Riesgos / notas |"
)


def test_description_literal_inside_project_description_block() -> None:
    """El user renderizado incluye la descripción tal cual entre las etiquetas XML."""
    desc = 'Literal con ñ, "comillas", <tag> y & entidades no escapadas en el JSON.'
    _system, user = render_estimation_prompt(_make_request(description=desc))
    assert "<project_description>" in user
    assert "</project_description>" in user
    i = user.index("<project_description>") + len("<project_description>")
    j = user.index("</project_description>")
    inner = user[i:j].strip("\n")
    assert inner == desc


def test_phases_table_system_has_format_keyword_narrative_does_not() -> None:
    """Instrucción de columnas de fases solo en output_format=phases_table, no en narrative."""
    sys_phases, _ = render_estimation_prompt(_make_request(output_format=OutputFormat.PHASES_TABLE))
    sys_narr, _ = render_estimation_prompt(_make_request(output_format=OutputFormat.NARRATIVE))
    assert _PHASES_TABLE_KEYWORD in sys_phases
    assert _PHASES_TABLE_KEYWORD not in sys_narr


def test_detailed_includes_per_phase_assumptions_instruction_summary_does_not() -> None:
    """Modo detailed exige supuestos por fase; summary no incluye esa instrucción."""
    sys_detailed, _ = render_estimation_prompt(_make_request(detail_level=DetailLevel.DETAILED))
    sys_summary, _ = render_estimation_prompt(_make_request(detail_level=DetailLevel.SUMMARY))
    assert "Supuestos por fase" in sys_detailed
    assert "Supuestos por fase" not in sys_summary


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


def test_default_bundle_is_estimation_v2() -> None:
    assert DEFAULT_ESTIMATION_BUNDLE.public_id == "estimation-v2"
    assert ESTIMATION_PROMPT_VERSION == "estimation-v2"


def test_v2_system_includes_quality_and_checklist() -> None:
    system, _ = render_estimation_prompt(_make_request())
    assert "<pre_response_checklist>" in system
    assert "Calibración numérica" in system


def test_v1_bundle_skips_v2_only_blocks() -> None:
    system, _ = render_estimation_prompt(_make_request(), bundle=ESTIMATION_BUNDLE_V1)
    assert "<pre_response_checklist>" not in system
    assert "Calibración numérica" not in system


def test_get_estimation_bundle_by_public_id() -> None:
    assert get_estimation_bundle("estimation-v1").template_subdir == "v1"
    assert get_estimation_bundle("estimation-v2").template_subdir == "v2"
