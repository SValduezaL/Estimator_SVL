"""Tests de políticas de escritura de caché."""

from __future__ import annotations

from app.cache.policies import is_result_cacheable
from app.guardrails.filters import build_safe_fallback
from app.schemas.estimation_common import DetailLevel, ProjectType
from tests.conftest import _STUB_RESULT


def test_stub_result_is_cacheable() -> None:
    assert is_result_cacheable(_STUB_RESULT) is True


def test_safe_fallback_not_cacheable() -> None:
    fb = build_safe_fallback(
        project_type=ProjectType.MOBILE_APP,
        detail_level=DetailLevel.MEDIUM,
    )
    assert is_result_cacheable(fb) is False
