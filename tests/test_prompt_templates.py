"""Tests deterministas de plantillas Jinja2 v3 (sin llamadas al LLM)."""

from __future__ import annotations

import json

import pytest
from jinja2 import TemplateNotFound, UndefinedError

from app.foundation.prompts.loader import build_estimation_jinja_environment, render_estimation_prompt
from app.foundation.prompts.registry import (
    DEFAULT_ESTIMATION_BUNDLE,
    ESTIMATION_BUNDLE_V3,
    ESTIMATION_PROMPT_VERSION,
    get_estimation_bundle,
)
from app.domain.schemas.estimation_common import DetailLevel, ProjectType
from app.domain.schemas.estimation_request import EstimationRequest


def _make_request(**overrides: object) -> EstimationRequest:
    base = {
        "description": "Descripción mínima válida para tests de plantillas.",
        "project_type": ProjectType.WEB_SAAS,
        "detail_level": DetailLevel.MEDIUM,
    }
    base.update(overrides)
    return EstimationRequest(**base)


def test_description_literal_inside_project_description_block() -> None:
    desc = 'Literal con ñ, "comillas", <tag> y & entidades.'
    _system, user = render_estimation_prompt(_make_request(description=desc))
    assert "<project_description>" in user
    i = user.index("<project_description>") + len("<project_description>")
    j = user.index("</project_description>")
    assert user[i:j].strip("\n") == desc


def test_v3_system_includes_json_and_reasoning_format() -> None:
    system, _ = render_estimation_prompt(_make_request())
    assert "estimation.v1" in system
    assert "<reasoning_format>" in system
    assert "reasoning" in system.lower()
    assert "output_format" not in system


def test_v3_user_has_no_output_format() -> None:
    _, user = render_estimation_prompt(_make_request())
    assert "<output_format>" not in user
    assert "<detail_level>medium</detail_level>" in user


def test_examples_inject_three_json_blocks() -> None:
    system, _ = render_estimation_prompt(_make_request())
    assert system.count("<reference_estimation") == 3
    assert system.count("<example_json>") == 3
    assert '"phases"' in system


def test_few_shots_follow_project_type() -> None:
    sm, _ = render_estimation_prompt(_make_request(project_type=ProjectType.MOBILE_APP))
    sw, _ = render_estimation_prompt(_make_request(project_type=ProjectType.WEB_SAAS))
    assert "Flutter" in sm or "móvil" in sm.lower()
    assert "tenant" in sw.lower() or "saas" in sw.lower()


def test_detail_level_changes_reasoning_instructions() -> None:
    sys_s, _ = render_estimation_prompt(_make_request(detail_level=DetailLevel.SUMMARY))
    sys_d, _ = render_estimation_prompt(_make_request(detail_level=DetailLevel.DETAILED))
    assert "100–700" in sys_s
    assert "400–4000" in sys_d


def test_v3_system_documents_phases_stack() -> None:
    system, _ = render_estimation_prompt(_make_request())
    assert "<phases_stack>" in system
    assert "phases[].stack" in system


def test_example_json_includes_stack_per_phase() -> None:
    env = build_estimation_jinja_environment()
    raw = env.globals["example_json"]("web_saas", 1)
    data = json.loads(raw)
    for phase in data["phases"]:
        assert isinstance(phase["stack"], list)
        assert len(phase["stack"]) >= 1


def test_example_json_filter_produces_valid_json() -> None:
    env = build_estimation_jinja_environment()
    raw = env.globals["example_json"]("web_saas", 1)
    data = json.loads(raw)
    assert "phases" in data
    assert "reasoning" in data


def test_strictundefined_errors_on_unknown_variable() -> None:
    env = build_estimation_jinja_environment()
    tmpl = env.from_string("{{ variable_inexistente }}")
    with pytest.raises(UndefinedError):
        tmpl.render()


def test_unknown_version_raises_template_not_found() -> None:
    with pytest.raises(TemplateNotFound):
        render_estimation_prompt(_make_request(), version="v999_nonexistent")


def test_default_bundle_is_v3_structured() -> None:
    assert DEFAULT_ESTIMATION_BUNDLE.public_id == "estimation-v3-structured"
    assert ESTIMATION_PROMPT_VERSION == "estimation-v3-structured"


def test_get_estimation_bundle_by_public_id() -> None:
    assert get_estimation_bundle("estimation-v3-structured").template_subdir == "v3"
    assert get_estimation_bundle(ESTIMATION_BUNDLE_V3.public_id) == ESTIMATION_BUNDLE_V3
