"""Observabilidad structlog y contadores in-memory para caché."""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Iterator

import structlog

log = structlog.get_logger(__name__)

_metrics: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def increment_cache_metric(name: str, outcome: str) -> None:
    _metrics[name][outcome] += 1


def get_cache_metrics() -> dict[str, dict[str, int]]:
    return {k: dict(v) for k, v in _metrics.items()}


def reset_cache_metrics() -> None:
    _metrics.clear()


def log_cache_event(event: str, **kwargs: Any) -> None:
    log.info(event, log_category="technical", **kwargs)


@contextmanager
def cache_timer(event: str, **kwargs: Any) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_cache_event(event, latency_ms=latency_ms, **kwargs)
