"""Tests del endpoint multipart /sessions/{session_id}/estimate."""

from __future__ import annotations

import pytest

from tests.test_estimate_endpoint import TRANSCRIPTION


def test_session_estimate_accepts_multipart_and_injects_attachment_text(
    client,
    litellm_stub_log: list[dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.routers.sessions as sessions_router

    monkeypatch.setattr(
        sessions_router,
        "extract_text",
        lambda **_kwargs: "Texto extraido del PDF",
    )

    session_id = client.post("/api/v1/sessions").json()["session_id"]
    response = client.post(
        f"/api/v1/sessions/{session_id}/estimate",
        data={
            "description": TRANSCRIPTION,
            "project_type": "web_saas",
            "detail_level": "medium",
        },
        files=[("files", ("scope.pdf", b"%PDF-1.7 fake", "application/pdf"))],
    )
    assert response.status_code == 200
    user_content = next(
        m["content"] for m in litellm_stub_log[0]["messages"] if m["role"] == "user"
    )
    assert TRANSCRIPTION in user_content
    assert "Texto extraido del PDF" in user_content


def test_session_estimate_rejects_unsupported_attachment(client) -> None:
    session_id = client.post("/api/v1/sessions").json()["session_id"]
    response = client.post(
        f"/api/v1/sessions/{session_id}/estimate",
        data={
            "description": TRANSCRIPTION,
            "project_type": "web_saas",
            "detail_level": "medium",
        },
        files=[("files", ("scope.txt", b"plain text", "text/plain"))],
    )
    assert response.status_code == 415
