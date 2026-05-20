"""Ventana principal de chat."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.components.chat.chat_message import render_chat_message
from frontend.components.common.empty_state import empty_state


def render_chat_window(messages: list[dict[str, Any]]) -> None:
    if not messages:
        empty_state(
            "Sin mensajes",
            "Envía una descripción del proyecto para iniciar la conversación.",
        )
        return

    container = st.container(height=520, border=False)
    with container:
        for msg in messages:
            render_chat_message(msg)
