"""Tests del orquestador de salida."""

from app.foundation.guardrails.output import run_output_guardrails
from app.domain.schemas.estimation_common import DetailLevel, ProjectType
from tests.conftest import _STUB_RESULT
from tests.foundation.guardrails.conftest import guardrails_disabled_settings, guardrails_strict_settings


def test_output_disabled_passthrough(guardrails_disabled_settings) -> None:
    out = run_output_guardrails(
        _STUB_RESULT,
        settings=guardrails_disabled_settings,
        detail_level=DetailLevel.MEDIUM,
        project_type=ProjectType.WEB_SAAS,
    )
    assert out is _STUB_RESULT


def test_output_runs_validators(guardrails_strict_settings) -> None:
    out = run_output_guardrails(
        _STUB_RESULT,
        settings=guardrails_strict_settings,
        detail_level=DetailLevel.MEDIUM,
        project_type=ProjectType.WEB_SAAS,
        description="test",
    )
    assert out.summary
