"""Tests de caché Redis (fakeredis) con LLM estructurado dobleado en conftest."""

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

from tests.conftest import _STUB_RESULT
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


def test_second_identical_request_is_cache_hit(
    client_with_redis_cache: TestClient,
    litellm_stub_log: list[dict],
) -> None:
    r1 = client_with_redis_cache.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["cache_hit"] is False
    assert len(litellm_stub_log) == 1

    r2 = client_with_redis_cache.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["cache_hit"] is True
    assert len(litellm_stub_log) == 1
    assert data2["result"]["total_cost_eur"] == data1["result"]["total_cost_eur"]


def test_cache_stores_structured_result(
    client_with_redis_cache: TestClient,
    litellm_stub_log: list[dict],
) -> None:
    client_with_redis_cache.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert _STUB_RESULT.total_cost_eur > 0
