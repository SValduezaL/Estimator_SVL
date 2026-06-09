"""Tests del orquestador exact → semantic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fakeredis import FakeRedis

from app.generation.cag.embeddings import FakeEmbeddingProvider
from app.generation.cag.exact import EstimationExactCache
from app.generation.cag.orchestrator import EstimationCacheOrchestrator, build_cache_context
from app.generation.cag.types import CachedPayload
from app.foundation.prompts.registry import DEFAULT_ESTIMATION_BUNDLE
from app.domain.schemas.estimation_common import DetailLevel, ProjectType
from app.domain.schemas.estimation_request import EstimationRequest
from tests.conftest import _STUB_RESULT


def test_lookup_exact_before_semantic(cache_test_settings) -> None:
    exact = EstimationExactCache(FakeRedis(decode_responses=True), ttl=60)
    ctx = build_cache_context(
        request=EstimationRequest(
            description="test orchestrator exact cache path description",
            project_type=ProjectType.WEB_SAAS,
            detail_level=DetailLevel.MEDIUM,
        ),
        bundle=DEFAULT_ESTIMATION_BUNDLE,
        schema_version="estimation.v1:guardrails.v1",
        model="gpt-4o-mini",
        max_tokens=800,
        thinking_budget=None,
    )
    payload = CachedPayload(
        result=_STUB_RESULT,
        model="gpt-4o-mini",
        provider="openai",
        finish_reason="stop",
        usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        cost_usd=0.0,
    )
    exact.store(ctx, payload)

    embed = FakeEmbeddingProvider(dimensions=8)
    mock_semantic = MagicMock()
    mock_semantic.lookup.return_value = MagicMock(hit=False)

    orch = EstimationCacheOrchestrator(
        settings=cache_test_settings,
        exact=exact,
        semantic=mock_semantic,
        embedding_provider=embed,
    )
    result = orch.lookup(ctx)
    assert result.hit is True
    assert result.source.value == "exact"
    mock_semantic.lookup.assert_not_called()


def test_semantic_lookup_receives_precomputed_embedding(cache_test_settings) -> None:
    exact = EstimationExactCache(FakeRedis(decode_responses=True), ttl=60)
    embed = FakeEmbeddingProvider(dimensions=8)
    ctx = build_cache_context(
        request=EstimationRequest(
            description="paraphrase test for semantic embedding reuse",
            project_type=ProjectType.MOBILE_APP,
            detail_level=DetailLevel.MEDIUM,
        ),
        bundle=DEFAULT_ESTIMATION_BUNDLE,
        schema_version="estimation.v1:guardrails.v1",
        model="gpt-4o-mini",
        max_tokens=800,
        thinking_budget=None,
    )
    mock_semantic = MagicMock()
    mock_semantic.lookup.return_value = MagicMock(hit=False)
    orch = EstimationCacheOrchestrator(
        settings=cache_test_settings,
        exact=exact,
        semantic=mock_semantic,
        embedding_provider=embed,
    )
    orch.lookup(ctx)
    mock_semantic.lookup.assert_called_once()
    call_kwargs = mock_semantic.lookup.call_args.kwargs
    assert call_kwargs["embedding"] is not None
    assert len(call_kwargs["embedding"]) == 8
