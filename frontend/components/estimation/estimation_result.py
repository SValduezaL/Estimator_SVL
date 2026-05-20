"""Visualización de EstimationResult."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.components.common.stat_card import stat_card
from frontend.components.estimation.phases_table import render_phases_table
from frontend.components.estimation.reasoning_block import render_reasoning


def render_estimation_inline(result: dict[str, Any]) -> None:
    st.markdown(f"**{result.get('summary', '')}**")
    c1, c2, c3 = st.columns(3)
    with c1:
        stat_card("Confianza", f"{result.get('confidence_pct', 0)} %")
    with c2:
        stat_card("Duración", f"{result.get('total_duration_weeks', 0)} sem")
    with c3:
        stat_card(
            "Coste total",
            f"{int(result.get('total_cost_eur', 0)):,} EUR".replace(",", "."),
        )
    phases = result.get("phases") or []
    if phases:
        st.markdown("#### Fases")
        render_phases_table(phases)
    with st.expander("Reasoning", expanded=False):
        render_reasoning(str(result.get("reasoning", "")))
