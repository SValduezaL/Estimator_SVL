"""Tests de caché Redis (fakeredis) con LiteLLM dobleado en conftest."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_estimation_cache
from app.main import app
from app.services.llm_cache import EstimationCache
from app.services.llm_wrapper import LLMWrapper

from tests.conftest import _LITELLM_STUB_COMPLETION_MARKDOWN
from tests.test_estimate_endpoint import ESTIMATE_PAYLOAD, TRANSCRIPTION


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test-pytest",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_models_by_provider={
            "openai": ["gpt-4o-mini", "gpt-4o"],
            "anthropic": ["claude-haiku-4-5"],
        },
    )


@pytest.fixture
def client_with_redis_cache(
    test_settings: Settings,
    litellm_stub_log: list[dict],
) -> Iterator[TestClient]:
    cache = EstimationCache(FakeRedis(decode_responses=True), ttl=3600)
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_estimation_cache] = lambda: cache
    yield TestClient(app)
    app.dependency_overrides.clear()


def _router_calls(log: list[dict]) -> int:
    return sum(1 for c in log if c.get("source") == "router")


def test_second_identical_request_is_cache_hit(
    client_with_redis_cache: TestClient,
    litellm_stub_log: list[dict],
) -> None:
    r1 = client_with_redis_cache.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["cache_hit"] is False
    assert _router_calls(litellm_stub_log) == 1

    r2 = client_with_redis_cache.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["cache_hit"] is True
    assert _router_calls(litellm_stub_log) == 1
    assert data2["text"] == _LITELLM_STUB_COMPLETION_MARKDOWN


@pytest.fixture
def client_redis_dispatch_tracked(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    litellm_stub_log: list[dict],
) -> Iterator[tuple[TestClient, list[int]]]:
    dispatches: list[int] = []
    orig = LLMWrapper._dispatch

    def counting_dispatch(self: LLMWrapper, *, model_override: str | None = None, **kwargs: object) -> object:
        dispatches.append(1)
        return orig(self, model_override=model_override, **kwargs)

    monkeypatch.setattr(LLMWrapper, "_dispatch", counting_dispatch)
    cache = EstimationCache(FakeRedis(decode_responses=True), ttl=3600)
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_estimation_cache] = lambda: cache
    yield TestClient(app), dispatches
    app.dependency_overrides.clear()


def test_two_distinct_descriptions_trigger_two_dispatches(
    client_redis_dispatch_tracked: tuple[TestClient, list[int]],
) -> None:
    client, dispatches = client_redis_dispatch_tracked
    r1 = client.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert r1.status_code == 200
    body2 = {**ESTIMATE_PAYLOAD, "description": TRANSCRIPTION + " (variante B)"}
    r2 = client.post("/api/v1/estimate", json=body2)
    assert r2.status_code == 200
    assert len(dispatches) == 2


def test_after_cache_fill_second_identical_request_is_hit(
    client_redis_dispatch_tracked: tuple[TestClient, list[int]],
    litellm_stub_log: list[dict],
) -> None:
    """Primera petición llena caché; la segunda idéntica no vuelve a llamar al LLM."""
    client, dispatches = client_redis_dispatch_tracked
    r = client.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert r.status_code == 200
    assert _router_calls(litellm_stub_log) == 1
    assert len(dispatches) == 1

    r2 = client.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert r2.status_code == 200
    data = r2.json()
    assert dispatches == [1]
    assert data["cache_hit"] is True
    assert data["text"] == _LITELLM_STUB_COMPLETION_MARKDOWN
