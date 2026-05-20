"""Paneles de error."""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from frontend.api.client import ApiError


def render_api_error(error: Any) -> None:
    if isinstance(error, ApiError):
        status = error.status_code
        title = "Error de API"
        if status == 404:
            title = "Sesión no encontrada"
        elif status == 410:
            title = "Sesión expirada"
        elif status == 502:
            title = "Fallo del servicio LLM"
        elif status is None:
            title = "API no disponible"
        detail = error.detail or str(error)
        request_id = error.request_id
    else:
        title = "Error inesperado"
        detail = str(error)
        request_id = None
        status = None

    rid_line = f"<div><b>Request ID:</b> {escape(request_id)}</div>" if request_id else ""
    status_line = f"<div><b>HTTP:</b> {status}</div>" if status else ""
    st.markdown(
        f"<div class='est-error-box'>"
        f"<strong>{escape(title)}</strong>"
        f"{status_line}"
        f"<div style='margin-top:0.35rem'>{escape(detail)}</div>"
        f"{rid_line}"
        f"</div>",
        unsafe_allow_html=True,
    )
