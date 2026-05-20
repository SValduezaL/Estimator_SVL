"""Estados vacíos."""

from __future__ import annotations

import streamlit as st


def empty_state(title: str, message: str) -> None:
    st.markdown(
        f"<div class='est-empty'><h3>{title}</h3><p>{message}</p></div>",
        unsafe_allow_html=True,
    )
