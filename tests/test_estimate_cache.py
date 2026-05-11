"""Tests de caché Redis (fakeredis) con LiteLLM dobleado en conftest."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_estimation_cache
from app.main import app
from app.services.llm_cache import EstimationCache
from app.services.llm_wrapper import LLMWrapper

from tests.test_estimate_endpoint import TRANSCRIPTION


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
    payload = {"transcription": TRANSCRIPTION}
    r1 = client_with_redis_cache.post("/api/v1/estimate", json=payload)
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["cache_hit"] is False
    assert b1["provider"] == "openai"

    r2 = client_with_redis_cache.post("/api/v1/estimate", json=payload)
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["cache_hit"] is True
    assert b2["estimation"] == b1["estimation"]
    assert _router_calls(litellm_stub_log) == 1


def test_skip_cache_second_request_still_calls_llm(
    client_with_redis_cache: TestClient,
    litellm_stub_log: list[dict],
) -> None:
    payload = {"transcription": TRANSCRIPTION}
    assert client_with_redis_cache.post("/api/v1/estimate", json=payload).status_code == 200
    r2 = client_with_redis_cache.post(
        "/api/v1/estimate",
        json={**payload, "skip_cache": True},
    )
    assert r2.status_code == 200
    assert r2.json()["cache_hit"] is False
    assert _router_calls(litellm_stub_log) == 2


@pytest.fixture
def client_redis_stream_tracked(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    litellm_stub_log: list[dict],
) -> Iterator[tuple[TestClient, list[int]]]:
    stream_dispatches: list[int] = []
    orig = LLMWrapper._dispatch

    def counting_dispatch(self: LLMWrapper, *, model_override: str | None = None, **kwargs: object) -> object:
        if kwargs.get("stream"):
            stream_dispatches.append(1)
        return orig(self, model_override=model_override, **kwargs)

    monkeypatch.setattr(LLMWrapper, "_dispatch", counting_dispatch)
    cache = EstimationCache(FakeRedis(decode_responses=True), ttl=3600)
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_estimation_cache] = lambda: cache
    yield TestClient(app), stream_dispatches
    app.dependency_overrides.clear()


def _metrics_cache_hit(raw_sse: str) -> bool | None:
    m = re.search(r"event:\s*metrics\s*\ndata:\s*(\{.*)", raw_sse, re.DOTALL)
    if not m:
        return None
    line = m.group(1).split("\n")[0]
    try:
        return bool(json.loads(line).get("cache_hit"))
    except json.JSONDecodeError:
        return None


def test_stream_second_identical_request_is_cache_hit(
    client_redis_stream_tracked: tuple[TestClient, list[int]],
) -> None:
    client, stream_dispatches = client_redis_stream_tracked
    body = {"transcription": TRANSCRIPTION}
    with client.stream("POST", "/api/v1/estimate/stream", json=body) as r1:
        assert r1.status_code == 200
        raw1 = r1.read().decode("utf-8")
    assert len(stream_dispatches) == 1
    assert _metrics_cache_hit(raw1) is False

    with client.stream("POST", "/api/v1/estimate/stream", json=body) as r2:
        assert r2.status_code == 200
        raw2 = r2.read().decode("utf-8")
    assert len(stream_dispatches) == 1
    assert _metrics_cache_hit(raw2) is True
    assert "stream-chunk" in raw2


def test_stream_skip_cache_bypasses_read(
    client_redis_stream_tracked: tuple[TestClient, list[int]],
) -> None:
    client, stream_dispatches = client_redis_stream_tracked
    body = {"transcription": TRANSCRIPTION}
    with client.stream("POST", "/api/v1/estimate/stream", json=body) as r1:
        assert r1.status_code == 200
        r1.read()
    with client.stream(
        "POST",
        "/api/v1/estimate/stream",
        json={**body, "skip_cache": True},
    ) as r2:
        assert r2.status_code == 200
        raw2 = r2.read().decode("utf-8")
    assert len(stream_dispatches) == 2
    assert _metrics_cache_hit(raw2) is False


def test_post_estimate_then_stream_reuses_cache_without_streaming_llm(
    client_redis_stream_tracked: tuple[TestClient, list[int]],
    litellm_stub_log: list[dict],
) -> None:
    client, stream_dispatches = client_redis_stream_tracked
    body = {"transcription": TRANSCRIPTION}
    assert client.post("/api/v1/estimate", json=body).status_code == 200
    assert _router_calls(litellm_stub_log) == 1

    with client.stream("POST", "/api/v1/estimate/stream", json=body) as r:
        assert r.status_code == 200
        raw = r.read().decode("utf-8")
    assert stream_dispatches == []
    assert _metrics_cache_hit(raw) is True
    assert "onboarding SaaS B2B" in raw
    assert "### Desglose de tareas" in raw
