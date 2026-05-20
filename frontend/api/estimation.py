"""Cliente de estimaciones."""

from __future__ import annotations

from typing import Any

import httpx

from frontend.api.client import ApiError, BaseApiClient


class EstimationClient(BaseApiClient):
    def estimate(
        self,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> tuple[dict[str, Any], httpx.Response]:
        data, response = self._request(
            "POST",
            "/api/v1/estimate",
            json=payload,
            request_id=request_id,
        )
        if "result" not in data:
            raise ApiError(
                message="Malformed estimation response",
                request_id=response.headers.get("X-Request-ID"),
            )
        return data, response
