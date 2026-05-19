"""Tests HTTP de caché semántica (embedding fake + índice mockeado)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient

from app.cache.embeddings import FakeEmbeddingProvider
from app.cache.exact import EstimationExactCache
from app.cache.orchestrator import EstimationCacheOrchestrator
from app.cache.semantic import EstimationSemanticCache
from app.config import Settings, get_settings
from app.dependencies import get_cache_orchestrator
from app.main import app
from tests.test_estimate_endpoint import ESTIMATE_PAYLOAD

PARAPHRASE_PAYLOAD = {
    **ESTIMATE_PAYLOAD,
    "description": (
        "Aplicación móvil con login, chat en tiempo real y notificaciones push "
        "para iOS y Android."
    ),
}


@pytest.fixture
def semantic_test_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test-pytest",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_models_by_provider={"openai": ["gpt-4o-mini"]},
        guardrails_enabled=False,
        redis_url="redis://fake",
        semantic_cache_enabled=True,
        semantic_cache_log_only=False,
        semantic_cache_threshold=0.5,
        semantic_embedding_provider="fake",
        semantic_embedding_dimensions=8,
    )


@pytest.fixture
def client_semantic_cache(
    semantic_test_settings: Settings,
    litellm_stub_log: list[dict],
) -> Iterator[tuple[TestClient, EstimationCacheOrchestrator]]:
    exact = EstimationExactCache(FakeRedis(decode_responses=True), ttl=3600)
    embed = FakeEmbeddingProvider(dimensions=8)
    mock_index = MagicMock()
    mock_index.query.return_value = []
    mock_index.load = MagicMock()

    with patch("redisvl.index.SearchIndex") as mock_si:
        mock_si.from_dict.return_value = mock_index
        semantic = EstimationSemanticCache(
            redis_client=MagicMock(),
            embedding_provider=embed,
            settings=semantic_test_settings,
        )
        orchestrator = EstimationCacheOrchestrator(
            settings=semantic_test_settings,
            exact=exact,
            semantic=semantic,
            embedding_provider=embed,
        )
        app.dependency_overrides[get_settings] = lambda: semantic_test_settings
        app.dependency_overrides[get_cache_orchestrator] = lambda: orchestrator
        yield TestClient(app), orchestrator
    app.dependency_overrides.clear()


def test_semantic_hit_skips_llm(
    client_semantic_cache: tuple[TestClient, EstimationCacheOrchestrator],
    litellm_stub_log: list[dict],
) -> None:
    client, orch = client_semantic_cache
    import json

    from app.cache.types import CachedPayload
    from tests.conftest import _STUB_RESULT

    payload = CachedPayload(
        result=_STUB_RESULT,
        model="gpt-4o-mini",
        provider="openai",
        finish_reason="stop",
        usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        cost_usd=0.01,
    )
    stored = json.dumps(payload.to_redis_dict())

    # First request populates via LLM
    r1 = client.post("/api/v1/estimate", json=ESTIMATE_PAYLOAD)
    assert r1.status_code == 200
    assert r1.json()["cache_hit"] is False
    assert len(litellm_stub_log) == 1

    # Simulate semantic index hit for paraphrase
    assert orch._semantic is not None
    orch._semantic.index.query.return_value = [  # type: ignore[union-attr]
        {"result_json": stored, "vector_distance": 0.02}
    ]

    r2 = client.post("/api/v1/estimate", json=PARAPHRASE_PAYLOAD)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["cache_hit"] is True
    assert len(litellm_stub_log) == 1
