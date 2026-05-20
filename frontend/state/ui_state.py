"""Estado de UI (tabs, filtros, preferencias)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.styles.constants import TAB_CHAT


def init_ui_state() -> None:
    defaults: dict[str, Any] = {
        "active_main_tab": TAB_CHAT,
        "metrics_filter_call_type": "all",
        "metrics_filter_session": "all",
        "metrics_search": "",
        "observability_selected_index": 0,
        "prompt_preview_key": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
