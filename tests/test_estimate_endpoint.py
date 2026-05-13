"""Tests del endpoint de estimaciones (LiteLLM simulado vía stubs en conftest)."""

import pytest

from app.schemas.estimation import ESTIMATION_PROMPT_VERSION

TRANSCRIPTION = (
    "We need a small CRM with auth, contacts and roles. MVP six weeks. "
    "Extra text to satisfy min length validation for the API."
)

ESTIMATE_PAYLOAD = {
    "description": TRANSCRIPTION,
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "line_items",
}


def _first_router_kwargs(log: list[dict]) -> dict:
    for c in log:
        if c.get("source") == "router":
            return c
    raise AssertionError("no router completion")


def test_stream_emits_token_metrics_done(client, litellm_stub_log: list[dict]) -> None:
    with client.stream("POST", "/api/v1/estimate", json=ESTIMATE_PAYLOAD) as response:
        assert response.status_code == 200
        raw = response.read().decode("utf-8")

    assert "event: token" in raw
    assert "stream-chunk" in raw
    assert "event: metrics" in raw
    assert ESTIMATION_PROMPT_VERSION in raw
    assert "event: done" in raw
    assert "[DONE]" in raw
    assert sum(1 for c in litellm_stub_log if c.get("source") == "router") == 1

    messages = _first_router_kwargs(litellm_stub_log)["messages"]
    user = next(m["content"] for m in messages if m["role"] == "user")
    assert "<project_description>" in user
    assert "web_saas" in user
    assert "medium" in user
    assert "line_items" in user
    assert TRANSCRIPTION in user


@pytest.mark.parametrize(
    "field,bad",
    [
        ("project_type", "not_an_enum"),
        ("detail_level", "verbose"),
        ("output_format", "markdown"),
    ],
)
def test_estimate_rejects_invalid_enum(client, field: str, bad: str) -> None:
    body = {**ESTIMATE_PAYLOAD, field: bad}
    r = client.post("/api/v1/estimate", json=body)
    assert r.status_code == 422


def test_estimate_rejects_short_description(client) -> None:
    r = client.post(
        "/api/v1/estimate",
        json={**ESTIMATE_PAYLOAD, "description": "x" * 19},
    )
    assert r.status_code == 422
