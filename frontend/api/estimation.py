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

    def estimate_for_session_with_attachments(
        self,
        *,
        session_id: str,
        description: str,
        project_type: str,
        detail_level: str,
        attachments: list[tuple[str, bytes, str]] | None = None,
        request_id: str | None = None,
    ) -> tuple[dict[str, Any], httpx.Response]:
        files_payload = [
            ("files", (filename, content, content_type))
            for filename, content, content_type in (attachments or [])
        ]
        data, response = self._request(
            "POST",
            f"/api/v1/sessions/{session_id}/estimate",
            data={
                "description": description,
                "project_type": project_type,
                "detail_level": detail_level,
            },
            files=files_payload if files_payload else None,
            request_id=request_id,
        )
        if "result" not in data:
            raise ApiError(
                message="Malformed estimation response",
                request_id=response.headers.get("X-Request-ID"),
            )
        return data, response
