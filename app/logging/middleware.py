"""Middleware HTTP: request_id y logs de ciclo de vida."""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging.context import bind_request_context, clear_request_context

_log = structlog.get_logger(__name__)
_REQUEST_ID_HEADER = "X-Request-ID"


def _normalize_request_id(value: str | None) -> str:
    if value:
        candidate = value.strip()
        if "\n" in candidate or "\r" in candidate:
            return str(uuid.uuid4())
        if 1 <= len(candidate) <= 64:
            return candidate
    return str(uuid.uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _normalize_request_id(request.headers.get(_REQUEST_ID_HEADER))
        bind_request_context(
            request_id=request_id,
            http_method=request.method,
            http_path=request.url.path,
        )
        start = time.perf_counter()
        _log.info("http_request_started", log_category="technical")
        try:
            response = await call_next(request)
        except Exception:
            _log.exception("http_request_failed", log_category="technical", critical=True)
            raise
        else:
            duration_ms = int((time.perf_counter() - start) * 1000)
            response.headers[_REQUEST_ID_HEADER] = request_id
            _log.info(
                "http_request_completed",
                log_category="technical",
                http_status=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        finally:
            clear_request_context()
