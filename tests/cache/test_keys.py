"""Tests de buckets y claves exactas v2."""

from __future__ import annotations

from app.cache.keys import bucket_for_context, make_exact_key, output_format_for_bundle
from app.cache.orchestrator import build_cache_context
from app.prompts.registry import ESTIMATION_BUNDLE_V1, ESTIMATION_BUNDLE_V3, DEFAULT_ESTIMATION_BUNDLE
from app.schemas.estimation_common import DetailLevel, ProjectType
from app.schemas.estimation_request import EstimationRequest


def test_output_format_derived_from_bundle() -> None:
    assert output_format_for_bundle(ESTIMATION_BUNDLE_V1) == "line_items"
    assert output_format_for_bundle(ESTIMATION_BUNDLE_V3) == "structured"


def test_bucket_isolates_project_type() -> None:
    base = {
        "description": "same text for bucket isolation test case",
        "detail_level": DetailLevel.MEDIUM,
    }
    r1 = EstimationRequest(project_type=ProjectType.MOBILE_APP, **base)
    r2 = EstimationRequest(project_type=ProjectType.WEB_SAAS, **base)
    ctx1 = build_cache_context(
        request=r1,
        bundle=DEFAULT_ESTIMATION_BUNDLE,
        schema_version="estimation.v1:guardrails.v1",
        model="gpt-4o-mini",
        max_tokens=1000,
        thinking_budget=None,
    )
    ctx2 = build_cache_context(
        request=r2,
        bundle=DEFAULT_ESTIMATION_BUNDLE,
        schema_version="estimation.v1:guardrails.v1",
        model="gpt-4o-mini",
        max_tokens=1000,
        thinking_budget=None,
    )
    assert bucket_for_context(ctx1).as_tag() != bucket_for_context(ctx2).as_tag()


def test_exact_key_changes_with_description() -> None:
    ctx_a = build_cache_context(
        request=EstimationRequest(
            description="App movil con login y chat en tiempo real",
            project_type=ProjectType.MOBILE_APP,
            detail_level=DetailLevel.MEDIUM,
        ),
        bundle=DEFAULT_ESTIMATION_BUNDLE,
        schema_version="v1",
        model="m",
        max_tokens=100,
        thinking_budget=None,
    )
    ctx_b = build_cache_context(
        request=EstimationRequest(
            description="Otra descripcion completamente diferente aqui",
            project_type=ProjectType.MOBILE_APP,
            detail_level=DetailLevel.MEDIUM,
        ),
        bundle=DEFAULT_ESTIMATION_BUNDLE,
        schema_version="v1",
        model="m",
        max_tokens=100,
        thinking_budget=None,
    )
    assert make_exact_key(ctx_a) != make_exact_key(ctx_b)
