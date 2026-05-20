"""Tema y configuración de página Streamlit."""

from __future__ import annotations

import streamlit as st


def configure_page() -> None:
    st.set_page_config(
        page_title="Estimador CAG — Copiloto",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
