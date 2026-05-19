"""Tests de caché Redis (fakeredis) con LLM estructurado dobleado en conftest."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient

from app.cache import build_cache_context, make_exact_key
from app.cache.exact import EstimationExactCache
from app.cache.orchestrator import EstimationCacheOrchestrator
from app.cache.types import CachedPayload
from app.config import Settings, get_settings
from app.dependencies import get_cache_orchestrator
from app.main import app
from app.prompts.registry import DEFAULT_ESTIMATION_BUNDLE
from app.schemas.estimation_request import EstimationRequest
from app.services.llm_wrapper import CACHE_SCHEMA_VERSION

from tests.conftest import _STUB_RESULT
from tests.test_estimate_endpoint import ESTIMATE_PAYLOAD


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
        guardrails_enabled=False,
        redis_url="redis://fake",
    )


@pytest.fixture
def client_with_redis_cache(
    test_settings: Settings,
    litellm_stub_log: list[dict],
) -> Iterator[TestClient]:
    exact = EstimationExactCache(FakeRedis(decode_responses=True), ttl=3600)
    orchestrator = EstimationCacheOrchestrator(
        settings=test_settings,
        exact=exact,
        semantic=None,
        embedding_provider=None,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_cache_orchestrator] = lambda: orchestrator
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


def test_cache_hit_model_and_provider_match_first_response(
    client_with_redis_cache: TestClient,
    litellm_stub_log: list[dict],
) -> None:
    data1 = client_with_redis_cache.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD).json()
    data2 = client_with_redis_cache.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD).json()

    assert data2["cache_hit"] is True
    assert data2["model"] == data1["model"]
    assert data2["provider"] == data1["provider"]
    assert data2["model"] == "gpt-4o-mini"
    assert data2["provider"] == "openai"


def test_cache_hit_uses_stored_model_not_configured_primary(
    test_settings: Settings,
    litellm_stub_log: list[dict],
) -> None:
    """Regresión: no mezclar LLM_MODEL configurado con proveedor del fallback en caché."""
    fake_redis = FakeRedis(decode_responses=True)
    exact = EstimationExactCache(fake_redis, ttl=3600)
    orchestrator = EstimationCacheOrchestrator(
        settings=test_settings,
        exact=exact,
        semantic=None,
        embedding_provider=None,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_cache_orchestrator] = lambda: orchestrator

    request = EstimationRequest(**ESTIMATE_PAYLOAD)
    ctx = build_cache_context(
        request=request,
        bundle=DEFAULT_ESTIMATION_BUNDLE,
        schema_version=CACHE_SCHEMA_VERSION,
        model=test_settings.llm_model,
        max_tokens=test_settings.max_tokens,
        thinking_budget=None,
    )
    key = make_exact_key(ctx)
    payload = CachedPayload(
        result=_STUB_RESULT,
        model="claude-haiku-4-5",
        provider="anthropic",
        finish_reason="stop",
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        cost_usd=0.001,
    )
    exact.redis.set(key, __import__("json").dumps(payload.to_redis_dict()))

    try:
        with TestClient(app) as client:
            data = client.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD).json()
    finally:
        app.dependency_overrides.clear()

    assert data["cache_hit"] is True
    assert data["model"] == "claude-haiku-4-5"
    assert data["provider"] == "anthropic"
    assert len(litellm_stub_log) == 0
