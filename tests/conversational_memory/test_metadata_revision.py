"""Tests de revisión y retractación de metadata."""

from __future__ import annotations

import asyncio

import pytest

from app.memory.models import ProjectMetadata
from app.memory.service import refresh_metadata_from_turn
from app.memory.store import create_session


def test_technology_replacement(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_update(
        metadata: ProjectMetadata,
        user_turn: str,
        assistant_turn: str,
        client: object,
    ) -> tuple[ProjectMetadata, dict]:
        return ProjectMetadata(
            mentioned_technologies=["Node.js"],
            rejected_options=["Rails"],
        ), {"executed": True, "degraded": False, "cost_usd": 0.0, "total_tokens": 0}

    monkeypatch.setattr("app.memory.service.update_metadata_llm", fake_update)

    session = create_session()
    session.project_metadata = ProjectMetadata(mentioned_technologies=["Rails"])
    asyncio.run(
        refresh_metadata_from_turn(
            session,
            user_turn="We are no longer using Rails. We will use Node.js instead.",
            assistant_turn="{}",
            client=object(),
        )
    )
    assert session.project_metadata.mentioned_technologies == ["Node.js"]
    assert "Rails" in session.project_metadata.rejected_options


def test_fact_retraction_clears_field(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_update(
        metadata: ProjectMetadata,
        user_turn: str,
        assistant_turn: str,
        client: object,
    ) -> tuple[ProjectMetadata, dict]:
        return metadata.model_copy(update={"assumed_team_size": None}), {
            "executed": True,
            "degraded": False,
            "cost_usd": 0.0,
            "total_tokens": 0,
        }

    monkeypatch.setattr("app.memory.service.update_metadata_llm", fake_update)

    session = create_session()
    session.project_metadata = ProjectMetadata(assumed_team_size=5)
    asyncio.run(
        refresh_metadata_from_turn(
            session,
            user_turn="Forget the team size assumption",
            assistant_turn="{}",
            client=object(),
        )
    )
    assert session.project_metadata.assumed_team_size is None


def test_rejected_options_accumulated(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_update(
        metadata: ProjectMetadata,
        user_turn: str,
        assistant_turn: str,
        client: object,
    ) -> tuple[ProjectMetadata, dict]:
        return ProjectMetadata(rejected_options=["Kubernetes", "serverless"]), {
            "executed": True,
            "degraded": False,
            "cost_usd": 0.0,
            "total_tokens": 0,
        }

    monkeypatch.setattr("app.memory.service.update_metadata_llm", fake_update)

    session = create_session()
    asyncio.run(
        refresh_metadata_from_turn(
            session,
            user_turn="No k8s nor serverless",
            assistant_turn="{}",
            client=object(),
        )
    )
    assert session.project_metadata.rejected_options == ["Kubernetes", "serverless"]
