"""Desglose de costes."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.components.common.stat_card import stat_card
from frontend.utils.charts import bar_chart_by_call_type
from frontend.utils.formatting import format_usd


def render_cost_breakdown(agg: dict[str, Any]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        stat_card("Coste total", format_usd(agg["total_cost_usd"], 4))
    with c2:
        stat_card("Llamadas", str(agg["count"]))
    with c3:
        stat_card("Cache hit ratio", f"{agg['cache_hit_ratio'] * 100:.1f} %")
    with c4:
        stat_card("Latencia media", f"{agg['avg_latency_ms']:.0f} ms")

    by_type = agg.get("cost_by_type") or {}
    chart_data = bar_chart_by_call_type(by_type)
    if chart_data:
        st.markdown("#### Coste por tipo de llamada")
        st.bar_chart(chart_data)
