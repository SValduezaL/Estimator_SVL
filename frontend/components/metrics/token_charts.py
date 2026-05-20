"""Gráficos de tokens."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.utils.charts import tokens_stacked_series


def render_token_charts(rows: list[dict[str, Any]]) -> None:
    series = tokens_stacked_series(rows)
    if not series:
        st.caption("Sin datos de tokens.")
        return
    st.markdown("#### Tokens por tipo de llamada")
    for call_type, counts in series.items():
        st.markdown(f"**{call_type}**")
        st.bar_chart({"input": counts["input"], "output": counts["output"]})
