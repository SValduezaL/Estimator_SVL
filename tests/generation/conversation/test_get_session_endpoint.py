"""GET /api/v1/sessions/{session_id}."""

from __future__ import annotations


def test_get_session_returns_metadata_and_history(client) -> None:
    created = client.post("/api/v1/sessions").json()
    sid = created["session_id"]
    detail = client.get(f"/api/v1/sessions/{sid}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["session_id"] == sid
    assert body["history"] == []
    assert body["project_metadata"]["project_name"] is None
