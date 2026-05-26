"""Integración estimate + sesión (errores HTTP y metadata en prompt)."""

from __future__ import annotations

import pytest

from app.memory.models import ProjectMetadata
from app.memory.store import get_session, update_session
from tests.test_estimate_endpoint import ESTIMATE_PAYLOAD


def test_estimate_unknown_session_404(client) -> None:
    r = client.post(
        "/api/v1/estimate",
        json={**ESTIMATE_PAYLOAD, "session_id": "nonexistent-id"},
    )
    assert r.status_code == 404


def test_estimate_expired_session_410(client) -> None:
    from datetime import datetime, timedelta

    from app.memory.constants import SESSION_TTL_HOURS
    from app.memory.store import SESSIONS, create_session

    session = create_session()
    session.updated_at = datetime.utcnow() - timedelta(hours=SESSION_TTL_HOURS + 1)
    SESSIONS[session.session_id] = session

    r = client.post(
        "/api/v1/estimate",
        json={**ESTIMATE_PAYLOAD, "session_id": session.session_id},
    )
    assert r.status_code == 410


def test_estimate_injects_metadata_in_system_prompt(
    client,
    litellm_stub_log: list,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.routers.estimations as estimations_router
    from app.memory.store import update_session

    async def identity_persist(session, **kwargs):  # noqa: ANN001, ANN003
        return update_session(session), {
            "executed": False,
            "degraded": True,
            "cost_usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    monkeypatch.setattr(estimations_router, "persist_estimation_turn", identity_persist)

    session_id = client.post("/api/v1/sessions").json()["session_id"]
    session = get_session(session_id)
    session.project_metadata = ProjectMetadata(project_name="Acme Portal")
    update_session(session)

    client.post(
        "/api/v1/estimate",
        json={**ESTIMATE_PAYLOAD, "session_id": session_id},
    )

    system = litellm_stub_log[0]["messages"][0]["content"]
    assert "Project name: Acme Portal" in system
