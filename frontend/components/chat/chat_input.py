"""Entrada de chat y envío de estimación."""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from app.schemas.estimation import (
    DETAIL_LEVEL_LABELS,
    PROJECT_TYPE_LABELS,
    DetailLevel,
    EstimationRequest,
    ProjectType,
)
from frontend.api.client import ApiError
from frontend.api.estimation import EstimationClient
from frontend.api.sessions import SessionClient
from frontend.components.common.error_panel import render_api_error
from frontend.state.session_state import (
    clear_api_error,
    get_active_session_id,
    record_estimation_call,
    register_session,
    set_api_error,
)
from frontend.styles.constants import MIN_DESCRIPTION_LEN


def _submit_estimation(
    *,
    description: str,
    project_type: ProjectType,
    detail_level: DetailLevel,
    active: str,
    estimation_client: EstimationClient,
    session_client: SessionClient,
) -> None:
    desc = description.strip()
    if len(desc) < MIN_DESCRIPTION_LEN:
        st.error(f"Mínimo {MIN_DESCRIPTION_LEN} caracteres (tienes {len(desc)}).")
        return
    try:
        req = EstimationRequest(
            description=desc,
            project_type=project_type,
            detail_level=detail_level,
            session_id=active,
        )
    except Exception as exc:
        st.error(f"Validación: {exc}")
        return

    payload = req.model_dump(mode="json")
    clear_api_error()

    metadata_before: dict[str, Any] = {}
    try:
        before = session_client.get_session(active)
        metadata_before = before.get("project_metadata") or {}
    except ApiError as exc:
        if exc.status_code not in (404, 410):
            set_api_error(exc)
            render_api_error(exc)
            return

    t0 = time.perf_counter()
    try:
        with st.spinner("Generando estimación…"):
            data, http_resp = estimation_client.estimate(payload)
        latency = time.perf_counter() - t0
        request_id = http_resp.headers.get("X-Request-ID")

        metadata_after = metadata_before
        try:
            after = session_client.get_session(active)
            metadata_after = after.get("project_metadata") or metadata_before
            register_session(active)
        except ApiError:
            pass

        record_estimation_call(
            session_id=active,
            payload=payload,
            response=data,
            latency_seconds=latency,
            request_id=request_id,
            metadata_before=metadata_before if isinstance(metadata_before, dict) else {},
            metadata_after=metadata_after if isinstance(metadata_after, dict) else {},
        )
        st.rerun()
    except ApiError as exc:
        set_api_error(exc)
        render_api_error(exc)


def render_chat_input(
    *,
    estimation_client: EstimationClient,
    session_client: SessionClient,
) -> None:
    active = get_active_session_id()
    if not active:
        st.warning("Crea o selecciona una sesión en la barra lateral.")
        return

    c1, c2 = st.columns(2)
    with c1:
        project_type = st.selectbox(
            "Tipo de proyecto",
            options=list(ProjectType),
            format_func=lambda p: PROJECT_TYPE_LABELS[p],
            key="chat_project_type",
        )
    with c2:
        detail_level = st.selectbox(
            "Nivel de detalle",
            options=list(DetailLevel),
            format_func=lambda d: DETAIL_LEVEL_LABELS[d],
            key="chat_detail_level",
        )

    # Formulario en lugar de st.chat_input (evita fallo del chunk JS ChatInput.*.js).
    with st.form("chat_message_form", clear_on_submit=True):
        description = st.text_area(
            "Mensaje",
            height=120,
            placeholder="Describe alcance, stack, restricciones o cambios (mín. 20 caracteres)…",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Enviar estimación", type="primary", use_container_width=True)

    if submitted and description:
        _submit_estimation(
            description=description,
            project_type=project_type,
            detail_level=detail_level,
            active=active,
            estimation_client=estimation_client,
            session_client=session_client,
        )
