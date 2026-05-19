"""Decoradores de duración para observabilidad."""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import structlog

P = ParamSpec("P")
R = TypeVar("R")


def log_duration(
    *,
    event: str,
    log_category: str = "technical",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        log = structlog.get_logger(fn.__module__)

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                log.info(
                    event,
                    log_category=log_category,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                )

        return wrapper

    return decorator
