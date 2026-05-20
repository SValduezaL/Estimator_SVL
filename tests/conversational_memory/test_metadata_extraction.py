"""Tests de extracción de metadata (extractor LLM mockeado)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.memory.extractor import update_metadata_llm
from app.memory.models import ProjectMetadata
from app.memory.service import refresh_metadata_from_turn
from app.memory.store import create_session


def test_extractor_updates_project_name(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_update(
        metadata: ProjectMetadata,
        user_turn: str,
        assistant_turn: str,
        client: object,
    ) -> ProjectMetadata:
        return metadata.model_copy(update={"project_name": "CRM Acme"})

    monkeypatch.setattr("app.memory.service.update_metadata_llm", fake_update)

    session = create_session()
    asyncio.run(
        refresh_metadata_from_turn(
            session,
            user_turn="El proyecto se llama CRM Acme",
            assistant_turn='{"summary": "ok"}',
            client=object(),
        )
    )
    assert session.project_metadata.project_name == "CRM Acme"


def test_extractor_updates_technologies_scope_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_update(
        metadata: ProjectMetadata,
        user_turn: str,
        assistant_turn: str,
        client: object,
    ) -> ProjectMetadata:
        return ProjectMetadata(
            mentioned_technologies=["PostgreSQL", "React"],
            agreed_scope="MVP con auth y contactos",
            explicit_constraints=["Debe cumplir GDPR"],
        )

    monkeypatch.setattr("app.memory.service.update_metadata_llm", fake_update)

    session = create_session()
    asyncio.run(
        refresh_metadata_from_turn(
            session,
            user_turn="Stack React y PostgreSQL, MVP auth",
            assistant_turn="{}",
            client=object(),
        )
    )
    md = session.project_metadata
    assert md.mentioned_technologies == ["PostgreSQL", "React"]
    assert md.agreed_scope == "MVP con auth y contactos"
    assert md.explicit_constraints == ["Debe cumplir GDPR"]


def test_update_metadata_llm_validates_with_pydantic() -> None:
    class FakeResponse:
        output_text = (
            '{"project_name": "X", "mentioned_technologies": ["Go"], '
            '"explicit_constraints": [], "rejected_options": []}'
        )

    client = AsyncMock()
    client.responses.create = AsyncMock(return_value=FakeResponse())

    updated = asyncio.run(
        update_metadata_llm(
            ProjectMetadata(),
            "user",
            "assistant",
            client,
        )
    )
    assert updated.project_name == "X"
    assert updated.mentioned_technologies == ["Go"]
    client.responses.create.assert_awaited_once()
