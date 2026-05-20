"""Cliente de sesiones conversacionales."""

from __future__ import annotations

from typing import Any

import httpx

from frontend.api.client import ApiError, BaseApiClient


class SessionClient(BaseApiClient):
    def create_session(self, *, request_id: str | None = None) -> dict[str, Any]:
        data, _ = self._request("POST", "/api/v1/sessions", request_id=request_id)
        if "session_id" not in data:
            raise ApiError(message="Malformed session create response")
        return data

    def get_session(
        self,
        session_id: str,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        data, _ = self._request(
            "GET",
            f"/api/v1/sessions/{session_id}",
            request_id=request_id,
        )
        return data
