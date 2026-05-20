"""Bloque de reasoning."""

from __future__ import annotations

import streamlit as st


def render_reasoning(reasoning: str) -> None:
    if reasoning:
        st.markdown(reasoning)
    else:
        st.caption("Sin reasoning.")
