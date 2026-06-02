"""Cliente HTTP base con reintentos y errores tipados."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from collections.abc import Mapping

import httpx

log = logging.getLogger("estimator.frontend.api")


class ApiError(Exception):
    """Error de API con contexto HTTP.

    No usar ``@dataclass(frozen, slots)`` aquí: rompe el ``__exit__`` de
    ``st.spinner`` / ``contextlib`` al asignar ``__traceback__``.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        detail: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail
        self.request_id = request_id

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"HTTP {self.status_code}")
        if self.detail:
            parts.append(self.detail)
        return " — ".join(parts)


class BaseApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 300.0,
        connect_timeout: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=connect_timeout)
        self._max_retries = max(0, max_retries)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
        request_id: str | None = None,
    ) -> tuple[dict[str, Any], httpx.Response]:
        url = f"{self._base_url}{path}"
        rid = request_id or str(uuid.uuid4())
        headers = {"X-Request-ID": rid}
        if json is not None and files is None:
            headers["Content-Type"] = "application/json"
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                log.info(
                    "api_request",
                    extra={
                        "method": method,
                        "path": path,
                        "attempt": attempt + 1,
                        "request_id": rid,
                    },
                )
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.request(
                        method,
                        url,
                        json=json,
                        data=data,
                        files=files,
                        headers=headers,
                    )
                if response.status_code >= 400:
                    detail = _extract_detail(response)
                    raise ApiError(
                        message=f"API error on {method} {path}",
                        status_code=response.status_code,
                        detail=detail,
                        request_id=response.headers.get("X-Request-ID") or rid,
                    )
                data = response.json() if response.content else {}
                log.info(
                    "api_response",
                    extra={
                        "method": method,
                        "path": path,
                        "status": response.status_code,
                        "request_id": response.headers.get("X-Request-ID") or rid,
                    },
                )
                return data, response
            except ApiError:
                raise
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    raise ApiError(
                        message="Request timeout",
                        detail=str(exc),
                        request_id=rid,
                    ) from exc
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    raise ApiError(
                        message="Connection error",
                        detail=str(exc),
                        request_id=rid,
                    ) from exc

        raise ApiError(message="Request failed", detail=str(last_exc), request_id=rid)


def _extract_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("detail")
            if detail is not None:
                return str(detail)
    except Exception:
        pass
    text = (response.text or "").strip()
    return text[:2000] if text else f"HTTP {response.status_code}"
