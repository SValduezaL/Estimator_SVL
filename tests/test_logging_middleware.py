"""Tests del middleware de request_id."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

_REQUEST_ID = "client-correlation-id-12345"


def _test_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test-pytest",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        app_env="dev",
    )


def test_health_returns_x_request_id_header() -> None:
    app.dependency_overrides[get_settings] = lambda: _test_settings()
    try:
        with TestClient(app) as client:
            response = client.get("/health", headers={"X-Request-ID": _REQUEST_ID})
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == _REQUEST_ID
    finally:
        app.dependency_overrides.clear()


def test_health_generates_request_id_when_header_missing() -> None:
    app.dependency_overrides[get_settings] = lambda: _test_settings()
    try:
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        rid = response.headers.get("X-Request-ID")
        assert rid
        assert 1 <= len(rid) <= 64
    finally:
        app.dependency_overrides.clear()


def test_invalid_request_id_newline_is_replaced() -> None:
    app.dependency_overrides[get_settings] = lambda: _test_settings()
    try:
        with TestClient(app) as client:
            response = client.get("/health", headers={"X-Request-ID": "bad\nid"})
        rid = response.headers.get("X-Request-ID")
        assert rid != "bad\nid"
        assert "\n" not in rid
    finally:
        app.dependency_overrides.clear()
