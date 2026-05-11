"""Tests del endpoint de estimaciones (LiteLLM simulado vía stubs en conftest)."""

from collections.abc import Iterator

import pytest

from app.context.examples import CANONICAL_EXAMPLES
from app.services.llm_service import StreamEvent
from app.services.llm_wrapper import LLMWrapper

WELL_FORMED_MD = CANONICAL_EXAMPLES[0].estimation_markdown

TRANSCRIPTION = (
    "We need a small CRM with auth, contacts and roles. MVP six weeks. "
    "Extra text to satisfy min length validation for the API."
)


def _first_router_kwargs(log: list[dict]) -> dict:
    for c in log:
        if c.get("source") == "router":
            return c
    raise AssertionError("no router completion")


def test_post_estimate_returns_finish_reason(
    client, litellm_stub_log: list[dict]
) -> None:
    response = client.post("/api/v1/estimate", json={"transcription": TRANSCRIPTION})
    assert response.status_code == 200
    body = response.json()
    assert body["finish_reason"] == "stop"
    assert body["model"] == "gpt-4o-mini"
    assert body["provider"] == "openai"
    assert body["cache_hit"] is False
    assert body["validation"] is None
    assert body["usage"]["total_tokens"] == 1801
    assert sum(1 for c in litellm_stub_log if c.get("source") == "router") == 1


def test_evaluate_true_returns_validation(
    client, litellm_stub_log: list[dict]
) -> None:
    response = client.post(
        "/api/v1/estimate",
        json={"transcription": TRANSCRIPTION, "evaluate": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["validation"] is not None
    assert body["validation"]["score"] == 1.0
    assert body["validation"]["issues"] == []


def test_max_tokens_low_sets_finish_reason_length(
    client, litellm_stub_log: list[dict]
) -> None:
    response = client.post(
        "/api/v1/estimate",
        json={"transcription": TRANSCRIPTION, "max_tokens": 200},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["finish_reason"] == "length"
    assert body["validation"] is None
    assert _first_router_kwargs(litellm_stub_log)["max_tokens"] == 200


def test_example_format_json_in_system_prompt(
    client, litellm_stub_log: list[dict]
) -> None:
    response = client.post(
        "/api/v1/estimate",
        json={
            "transcription": TRANSCRIPTION,
            "example_format": "json",
            "num_examples": 2,
        },
    )
    assert response.status_code == 200
    messages = _first_router_kwargs(litellm_stub_log)["messages"]
    system = next(m["content"] for m in messages if m["role"] == "system")
    assert "Ejemplos de referencia (JSON):" in system


def test_model_override_passed_to_provider(
    client, litellm_stub_log: list[dict]
) -> None:
    response = client.post(
        "/api/v1/estimate",
        json={"transcription": TRANSCRIPTION, "model": "gpt-4o"},
    )
    assert response.status_code == 200
    assert any(
        c.get("source") == "litellm" and c.get("model") == "gpt-4o" for c in litellm_stub_log
    )


def test_use_examples_false_omits_examples_block(
    client, litellm_stub_log: list[dict]
) -> None:
    response = client.post(
        "/api/v1/estimate",
        json={"transcription": TRANSCRIPTION, "use_examples": False},
    )
    assert response.status_code == 200
    messages = _first_router_kwargs(litellm_stub_log)["messages"]
    sp = next(m["content"] for m in messages if m["role"] == "system")
    assert "EJEMPLO 1" not in sp
    assert "Ejemplos de referencia" not in sp


def test_invalid_model_returns_422(client, litellm_stub_log: list[dict]) -> None:
    response = client.post(
        "/api/v1/estimate",
        json={"transcription": TRANSCRIPTION, "model": "unknown-model-xyz"},
    )
    assert response.status_code == 422
    assert litellm_stub_log == []


def test_preprocessing_not_none_returns_422(client) -> None:
    response = client.post(
        "/api/v1/estimate",
        json={"transcription": TRANSCRIPTION, "preprocessing": "two_phase"},
    )
    assert response.status_code == 422


@pytest.fixture
def openai_stream_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_stream(
        self: LLMWrapper,
        **kwargs: object,
    ) -> Iterator[StreamEvent]:
        yield StreamEvent(type="chunk", data={"text": "Hola "})
        yield StreamEvent(type="chunk", data={"text": "mundo"})
        yield StreamEvent(
            type="done",
            data={
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 2,
                    "total_tokens": 3,
                },
                "usage_available": True,
            },
        )

    monkeypatch.setattr(LLMWrapper, "stream_events", fake_stream)


def test_stream_emits_token_metrics_done(
    client, openai_stream_fake: None
) -> None:
    with client.stream(
        "POST",
        "/api/v1/estimate/stream",
        json={"transcription": TRANSCRIPTION},
    ) as response:
        assert response.status_code == 200
        raw = response.read().decode("utf-8")

    assert "event: token" in raw
    assert "Hola " in raw or "mundo" in raw
    assert "event: metrics" in raw
    assert "event: done" in raw
    assert "[DONE]" in raw
