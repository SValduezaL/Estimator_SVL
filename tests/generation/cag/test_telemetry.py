"""Tests de métricas y contadores de caché."""

from __future__ import annotations

from app.generation.cag.telemetry import get_cache_metrics, increment_cache_metric, reset_cache_metrics


def test_cache_metrics_increment() -> None:
    reset_cache_metrics()
    increment_cache_metric("exact_cache", "hit")
    increment_cache_metric("exact_cache", "hit")
    increment_cache_metric("semantic_cache", "miss")
    metrics = get_cache_metrics()
    assert metrics["exact_cache"]["hit"] == 2
    assert metrics["semantic_cache"]["miss"] == 1
