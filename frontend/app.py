"""Punto de entrada de la aplicación Streamlit modular."""

from __future__ import annotations

import logging
import os

import streamlit as st
from dotenv import load_dotenv

from frontend.api.estimation import EstimationClient
from frontend.api.sessions import SessionClient
from frontend.components.chat.chat_input import render_chat_input
from frontend.components.chat.chat_window import render_chat_window
from frontend.components.chat.session_sidebar import render_session_sidebar
from frontend.api.client import ApiError
from frontend.components.common.error_panel import render_api_error
from frontend.components.memory.memory_panel import render_memory_panel
from frontend.components.metrics.metrics_dashboard import render_metrics_dashboard
from frontend.components.observability.debug_console import render_observability_console
from frontend.components.prompts.prompt_preview import render_prompt_tab
from frontend.state.session_state import (
    get_active_session_id,
    get_session_record,
    init_app_state,
)
from frontend.state.ui_state import init_ui_state
from frontend.styles.css import inject_global_css
from frontend.styles.constants import (
    TAB_CHAT,
    TAB_COSTS,
    TAB_MEMORY,
    TAB_OBSERVABILITY,
    TAB_PROMPT,
)
from frontend.styles.theme import configure_page

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("estimator.frontend")


def _api_base_url() -> str:
    return (
        os.getenv("ESTIMATOR_API_BASE_URL")
        or os.getenv("API_BASE_URL")
        or "http://localhost:8000"
    ).rstrip("/")


def run_app() -> None:
    configure_page()
    inject_global_css()
    init_app_state()
    init_ui_state()

    api_base = _api_base_url()
    session_client = SessionClient(api_base)
    estimation_client = EstimationClient(api_base)

    st.markdown(
        "<h1 style='margin-bottom:0.2rem'>Estimador CAG</h1>"
        "<p style='color:#94a3b8;margin-top:0'>Copiloto conversacional multi-sesión · estimación estructurada</p>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        render_session_sidebar(session_client=session_client, api_base=api_base)
        st.link_button("OpenAPI", f"{api_base}/docs", use_container_width=True)

    err = st.session_state.get("last_api_error")
    if err:
        render_api_error(
            ApiError(
                message=str(err.get("message", "Error")),
                status_code=err.get("status_code"),
                detail=err.get("detail"),
                request_id=err.get("request_id"),
            )
        )

    tabs = st.tabs([TAB_CHAT, TAB_MEMORY, TAB_COSTS, TAB_OBSERVABILITY, TAB_PROMPT])

    with tabs[0]:
        active = get_active_session_id()
        messages = []
        if active:
            rec = get_session_record(active)
            if rec:
                messages = rec.get("messages") or []
        render_chat_window(messages)
        render_chat_input(
            estimation_client=estimation_client,
            session_client=session_client,
        )

    with tabs[1]:
        render_memory_panel()

    with tabs[2]:
        render_metrics_dashboard()

    with tabs[3]:
        render_observability_console()

    with tabs[4]:
        render_prompt_tab()

    log.debug("render_complete", extra={"active_session": get_active_session_id()})
