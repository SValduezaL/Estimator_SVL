"""Tests de renderizado de prompts con metadata."""

from __future__ import annotations

from app.generation.conversation.models import ProjectMetadata
from app.foundation.prompts.loader import render_estimation_prompt
from app.domain.schemas.estimation_common import DetailLevel, ProjectType
from app.domain.schemas.estimation_request import EstimationRequest


def test_render_with_session_metadata() -> None:
    req = EstimationRequest(
        description="Descripción mínima válida para tests de plantillas.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
    )
    md = ProjectMetadata(project_name="Portal X")
    system, user = render_estimation_prompt(req, project_metadata=md)
    assert "Portal X" in system
    assert "<project_description>" in user
