"""Fixtures compartidas para tests de caché."""

from __future__ import annotations

import pytest

from app.generation.cag.embeddings import FakeEmbeddingProvider
from app.generation.cag.telemetry import reset_cache_metrics
from app.config import Settings


@pytest.fixture(autouse=True)
def _reset_cache_metrics() -> None:
    reset_cache_metrics()
    yield
    reset_cache_metrics()


@pytest.fixture
def cache_test_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_models_by_provider={"openai": ["gpt-4o-mini"]},
        redis_url="redis://fake",
        semantic_cache_enabled=True,
        semantic_cache_log_only=False,
        semantic_cache_threshold=0.85,
        semantic_embedding_provider="fake",
    )


@pytest.fixture
def fake_embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider(dimensions=8, model="fake-test")
