"""Propagación de request_id al executor y logs de estimación."""

from __future__ import annotations

import logging
from io import StringIO

from fastapi.testclient import TestClient

from app.logging.config import configure_logging

_ESTIMATE_PAYLOAD = {
    "description": "Aplicación web con autenticación, panel admin y API REST documentada.",
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "line_items",
}
_REQUEST_ID = "estimate-correlation-abc"


def test_estimate_response_includes_request_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/estimate",
        json=_ESTIMATE_PAYLOAD,
        headers={"X-Request-ID": _REQUEST_ID},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == _REQUEST_ID


def test_estimate_logs_contain_request_id(client: TestClient, test_settings) -> None:
    prod = test_settings.model_copy(update={"app_env": "prod"})
    configure_logging(prod, version="0.1.0-test")

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    root = logging.getLogger()
    handler.setFormatter(root.handlers[0].formatter)
    root.handlers.clear()
    root.addHandler(handler)

    response = client.post(
        "/api/v1/estimate",
        json=_ESTIMATE_PAYLOAD,
        headers={"X-Request-ID": _REQUEST_ID},
    )
    assert response.status_code == 200
    handler.flush()

    output = stream.getvalue()
    assert _REQUEST_ID in output
    assert "estimation_requested" in output
    assert "estimation_completed" in output
    assert "llm_generate_started" in output
