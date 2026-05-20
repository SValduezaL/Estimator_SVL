"""Tests de clientes API (httpx mock)."""

from __future__ import annotations

import httpx
import pytest

from frontend.api.client import ApiError
from frontend.api.estimation import EstimationClient
from frontend.api.sessions import SessionClient


def test_session_client_create(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(self, method, path, **kwargs):  # noqa: ANN001
        assert method == "POST"
        assert path == "/api/v1/sessions"
        return {"session_id": "abc-123"}, httpx.Response(200, json={"session_id": "abc-123"})

    monkeypatch.setattr(SessionClient, "_request", fake_request)
    data = SessionClient("http://test").create_session()
    assert data["session_id"] == "abc-123"


def test_estimation_client_requires_result(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(self, method, path, **kwargs):  # noqa: ANN001
        return {}, httpx.Response(200, json={})

    monkeypatch.setattr(EstimationClient, "_request", fake_request)
    with pytest.raises(ApiError):
        EstimationClient("http://test").estimate({"description": "x" * 20, "project_type": "web_saas", "detail_level": "medium"})


def test_api_error_on_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(self, method, path, **kwargs):  # noqa: ANN001
        raise ApiError(message="missing", status_code=404, detail="not found")

    monkeypatch.setattr(SessionClient, "_request", fake_request)
    with pytest.raises(ApiError) as exc:
        SessionClient("http://test").get_session("id")
    assert exc.value.status_code == 404
