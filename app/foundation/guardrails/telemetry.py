"""Observabilidad structlog y contadores in-memory para guardrails."""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Iterator

import structlog

from app.foundation.guardrails.types import FailurePolicy

log = structlog.get_logger(__name__)

_metrics: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def increment_guardrail_metric(name: str, outcome: str) -> None:
    """Contador en memoria (exportable a Prometheus más adelante)."""
    _metrics[name][outcome] += 1


def get_guardrail_metrics() -> dict[str, dict[str, int]]:
    return {k: dict(v) for k, v in _metrics.items()}


def reset_guardrail_metrics() -> None:
    _metrics.clear()


def log_guardrail_event(event: str, **kwargs: Any) -> None:
    log.info(event, log_category="guardrails", **kwargs)


def log_policy_applied(
    *,
    guardrail_name: str,
    policy: FailurePolicy,
    passed: bool,
    **kwargs: Any,
) -> None:
    outcome = "passed" if passed else policy.value
    increment_guardrail_metric(guardrail_name, outcome)
    log.info(
        "guardrail_policy_applied",
        log_category="guardrails",
        guardrail_name=guardrail_name,
        policy=policy.value,
        passed=passed,
        **kwargs,
    )


@contextmanager
def guardrail_timer(guardrail_name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        latency_ms = int((time.perf_counter() - start) * 1000)
        log.debug(
            "guardrail_check_completed",
            log_category="guardrails",
            guardrail_name=guardrail_name,
            latency_ms=latency_ms,
        )
