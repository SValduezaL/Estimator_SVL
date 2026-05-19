"""Tests del endpoint de estimaciones (LLM simulado vía stubs en conftest)."""

import pytest

from app.prompts.registry import ESTIMATION_PROMPT_VERSION
from app.schemas.estimation_common import DetailLevel
from tests.conftest import _STUB_RESULT

TRANSCRIPTION = (
    "We need a small CRM with auth, contacts and roles. MVP six weeks. "
    "Extra text to satisfy min length validation for the API."
)

ESTIMATE_PAYLOAD = {
    "description": TRANSCRIPTION,
    "project_type": "web_saas",
    "detail_level": "medium",
}


def test_estimate_returns_structured_json(client, litellm_stub_log: list[dict]) -> None:
    response = client.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert response.status_code == 200
    data = response.json()

    assert data["schema_version"] == "estimation.v1"
    assert data["result"]["summary"] == _STUB_RESULT.summary
    assert data["result"]["total_cost_eur"] == _STUB_RESULT.total_cost_eur
    assert len(data["result"]["phases"]) == len(_STUB_RESULT.phases)
    assert data["prompt_version"] == ESTIMATION_PROMPT_VERSION
    assert data["prompt_version_created_at"] == "2026-05-19"
    assert data["cache_hit"] is False
    assert data["usage"]["input_tokens"] == 1234
    assert "text" not in data
    assert len(litellm_stub_log) == 1
    assert litellm_stub_log[0]["detail_level"] == DetailLevel.MEDIUM
    user_content = next(
        m["content"] for m in litellm_stub_log[0]["messages"] if m["role"] == "user"
    )
    assert TRANSCRIPTION in user_content


@pytest.mark.parametrize(
    "field,bad",
    [
        ("project_type", "not_an_enum"),
        ("detail_level", "verbose"),
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
