"""Gráficos de latencia."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.utils.charts import latency_by_model


def render_latency_charts(rows: list[dict[str, Any]]) -> None:
    by_model = latency_by_model(rows)
    if by_model:
        st.markdown("#### Latencia media por modelo")
        st.bar_chart({k: round(v, 1) for k, v in by_model.items()})
    else:
        st.caption("Sin latencias registradas.")
