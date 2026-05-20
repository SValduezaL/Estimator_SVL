"""Tarjetas de métricas."""

from __future__ import annotations

import streamlit as st


def stat_card(label: str, value: str, *, hint: str | None = None) -> None:
    hint_html = f"<div style='font-size:0.7rem;opacity:0.65;margin-top:0.2rem'>{hint}</div>" if hint else ""
    st.markdown(
        f"<div class='est-card'>"
        f"<div class='est-stat-label'>{label}</div>"
        f"<div class='est-stat-value'>{value}</div>"
        f"{hint_html}"
        f"</div>",
        unsafe_allow_html=True,
    )
