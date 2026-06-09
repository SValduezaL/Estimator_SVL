"""Tests de inyección de project_metadata en el system prompt."""

from __future__ import annotations

from app.generation.conversation.models import ProjectMetadata
from app.foundation.prompts.loader import render_estimation_prompt
from app.domain.schemas.estimation_common import DetailLevel, ProjectType
from app.domain.schemas.estimation_request import EstimationRequest


def _request() -> EstimationRequest:
    return EstimationRequest(
        description="Descripción mínima válida para tests de plantillas.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
    )


def test_metadata_block_rendered_with_populated_fields() -> None:
    metadata = ProjectMetadata(
        project_name="Portal B2B",
        assumed_team_size=4,
        mentioned_technologies=["React", "PostgreSQL"],
        agreed_scope="MVP con facturación",
        explicit_constraints=["ISO 27001"],
        rejected_options=["MongoDB"],
    )
    system, _ = render_estimation_prompt(_request(), project_metadata=metadata)

    assert "<project_metadata>" in system
    assert "Project name: Portal B2B" in system
    assert "Assumed team size:" in system
    assert "4" in system
    assert "Technologies mentioned:" in system
    assert "React, PostgreSQL" in system
    assert "Agreed scope:" in system
    assert "Explicit constraints:" in system
    assert "- ISO 27001" in system
    assert "Rejected options:" in system
    assert "- MongoDB" in system


def test_empty_metadata_omits_block() -> None:
    system, _ = render_estimation_prompt(_request(), project_metadata=None)
    assert "<project_metadata>" not in system
    assert "Treat project_metadata as established facts" not in system


def test_partial_metadata_omits_empty_fields() -> None:
    metadata = ProjectMetadata(project_name="Solo nombre")
    system, _ = render_estimation_prompt(_request(), project_metadata=metadata)

    assert "Project name: Solo nombre" in system
    assert "Technologies mentioned:" not in system
    assert "Rejected options:" not in system


def test_authority_instruction_included_when_metadata_present() -> None:
    metadata = ProjectMetadata(agreed_scope="Alcance fijo")
    system, _ = render_estimation_prompt(_request(), project_metadata=metadata)

    assert "Treat project_metadata as established facts." in system
    assert "Do not contradict them unless the user explicitly revises them." in system
