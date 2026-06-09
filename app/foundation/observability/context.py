"""Contexto de request y trazas (contextvars + structlog)."""

from __future__ import annotations

import contextvars
from typing import Any

import structlog

_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)


def bind_request_context(**kwargs: Any) -> None:
    structlog.contextvars.bind_contextvars(**kwargs)


def set_otel_trace(trace_id: str | None, span_id: str | None) -> None:
    _trace_id.set(trace_id)
    _span_id.set(span_id)
    structlog.contextvars.bind_contextvars(trace_id=trace_id, span_id=span_id)


def get_trace_id() -> str | None:
    return _trace_id.get()


def get_span_id() -> str | None:
    return _span_id.get()


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
    _trace_id.set(None)
    _span_id.set(None)
