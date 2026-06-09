"""Procesadores structlog compartidos (redacción, metadatos, OTel)."""

from __future__ import annotations

from typing import Any

from app.logging.context import get_span_id, get_trace_id

_SENSITIVE_KEYS = frozenset({
    "api_key",
    "authorization",
    "description",
    "messages",
    "system_prompt",
    "user_message",
    "content",
    "password",
    "token",
})

_service_metadata: dict[str, str] = {}


def set_service_metadata(**metadata: str) -> None:
    """Metadatos de servicio inyectados en cada línea de log."""
    global _service_metadata
    _service_metadata = dict(metadata)


def redact_sensitive(
    _logger: object,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    for key in list(event_dict):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def add_service_context(
    _logger: object,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    event_dict.update(_service_metadata)
    return event_dict


def add_otel_context(
    _logger: object,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    trace_id = get_trace_id()
    span_id = get_span_id()
    event_dict["trace_id"] = trace_id
    event_dict["span_id"] = span_id
    return event_dict
