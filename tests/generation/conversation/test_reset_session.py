"""Tests de reset explícito vía POST /sessions."""

from __future__ import annotations

import pytest

from app.generation.conversation.models import Message, ProjectMetadata
from app.generation.conversation.store import get_session, update_session
from tests.test_estimate_endpoint import ESTIMATE_PAYLOAD


def test_post_sessions_returns_new_empty_session(client) -> None:
    r1 = client.post("/api/v1/sessions")
    r2 = client.post("/api/v1/sessions")

    assert r1.status_code == 200
    assert r2.status_code == 200
    id1 = r1.json()["session_id"]
    id2 = r2.json()["session_id"]
    assert id1 != id2

    s1 = get_session(id1)
    s2 = get_session(id2)
    assert s1.history == []
    assert s2.history == []
    assert s1.project_metadata.is_empty()
    assert s2.project_metadata.is_empty()


def test_new_session_after_estimate_starts_clean(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.estimation_service as estimations_router

    async def fake_persist(session, **kwargs):  # noqa: ANN001, ANN003
        session.project_metadata = ProjectMetadata(project_name="Dirty")
        session.history.append(Message(role="user", content="old"))
        return update_session(session), {
            "executed": False,
            "degraded": True,
            "cost_usd": 0.0,
            "total_tokens": 0,
        }

    monkeypatch.setattr(estimations_router, "persist_estimation_turn", fake_persist)

    old = client.post("/api/v1/sessions").json()["session_id"]
    resp = client.post(
        "/api/v1/estimate",
        json={**ESTIMATE_PAYLOAD, "session_id": old},
    )
    assert resp.status_code == 200

    reset = client.post("/api/v1/sessions").json()["session_id"]
    fresh = get_session(reset)
    assert fresh.history == []
    assert fresh.project_metadata.is_empty()
    assert reset != old


def test_estimate_with_session_injects_history(
    client,
    litellm_stub_log: list,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.domain.estimation_service as estimations_router

    async def identity_persist(session, **kwargs):  # noqa: ANN001, ANN003
        return update_session(session), {
            "executed": False,
            "degraded": True,
            "cost_usd": 0.0,
            "total_tokens": 0,
        }

    monkeypatch.setattr(estimations_router, "persist_estimation_turn", identity_persist)

    session_id = client.post("/api/v1/sessions").json()["session_id"]
    session = get_session(session_id)
    session.history = [
        Message(role="user", content="prev user"),
        Message(role="assistant", content="prev assistant"),
    ]
    update_session(session)

    client.post(
        "/api/v1/estimate",
        json={**ESTIMATE_PAYLOAD, "session_id": session_id},
    )

    messages = litellm_stub_log[0]["messages"]
    assert messages[1]["content"] == "prev user"
    assert messages[2]["content"] == "prev assistant"
    assert messages[3]["role"] == "user"
