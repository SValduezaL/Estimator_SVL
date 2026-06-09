"""Tests unitarios de EstimationSemanticCache (SearchIndex mockeado)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.generation.cag.orchestrator import build_cache_context
from app.generation.cag.semantic import EstimationSemanticCache
from app.generation.cag.types import CachedPayload
from app.foundation.prompts.registry import DEFAULT_ESTIMATION_BUNDLE
from app.domain.schemas.estimation_common import DetailLevel, ProjectType
from app.domain.schemas.estimation_request import EstimationRequest
from tests.conftest import _STUB_RESULT


@pytest.fixture
def cache_ctx():
    return build_cache_context(
        request=EstimationRequest(
            description="Mobile app with login and chat",
            project_type=ProjectType.MOBILE_APP,
            detail_level=DetailLevel.MEDIUM,
        ),
        bundle=DEFAULT_ESTIMATION_BUNDLE,
        schema_version="estimation.v1:guardrails.v1",
        model="gpt-4o-mini",
        max_tokens=800,
        thinking_budget=None,
    )


def test_semantic_hit_above_threshold(
    cache_test_settings,
    fake_embedding_provider,
    cache_ctx,
) -> None:
    payload = CachedPayload(
        result=_STUB_RESULT,
        model="gpt-4o-mini",
        provider="openai",
        finish_reason="stop",
        usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        cost_usd=0.0,
    )
    import json

    stored = json.dumps(payload.to_redis_dict())
    mock_index = MagicMock()
    mock_index.query.return_value = [
        {
            "result_json": stored,
            "vector_distance": 0.05,
        }
    ]

    with patch("redisvl.index.SearchIndex") as mock_si:
        mock_si.from_dict.return_value = mock_index
        cache = EstimationSemanticCache(
            redis_client=MagicMock(),
            embedding_provider=fake_embedding_provider,
            settings=cache_test_settings,
        )
        result = cache.lookup(cache_ctx, embedding=[0.1] * 8)

    assert result.hit is True
    assert result.similarity == pytest.approx(0.95, abs=0.01)
    assert result.payload is not None
    assert result.payload.result.summary == _STUB_RESULT.summary


def test_semantic_below_threshold(
    cache_test_settings,
    fake_embedding_provider,
    cache_ctx,
) -> None:
    mock_index = MagicMock()
    mock_index.query.return_value = [{"result_json": "{}", "vector_distance": 0.5}]

    with patch("redisvl.index.SearchIndex") as mock_si:
        mock_si.from_dict.return_value = mock_index
        cache = EstimationSemanticCache(
            redis_client=MagicMock(),
            embedding_provider=fake_embedding_provider,
            settings=cache_test_settings,
        )
        result = cache.lookup(cache_ctx, embedding=[0.1] * 8)

    assert result.hit is False
    assert result.similarity == pytest.approx(0.5, abs=0.01)


def test_semantic_log_only_returns_miss(
    cache_test_settings,
    fake_embedding_provider,
    cache_ctx,
) -> None:
    cache_test_settings.semantic_cache_log_only = True
    mock_index = MagicMock()
    mock_index.query.return_value = [
        {"result_json": "{}", "vector_distance": 0.01},
    ]

    with patch("redisvl.index.SearchIndex") as mock_si:
        mock_si.from_dict.return_value = mock_index
        cache = EstimationSemanticCache(
            redis_client=MagicMock(),
            embedding_provider=fake_embedding_provider,
            settings=cache_test_settings,
        )
        result = cache.lookup(cache_ctx, embedding=[0.1] * 8)

    assert result.hit is False
    assert result.log_only_would_hit is True
