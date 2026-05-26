"""Dashboard de costes y métricas."""

from __future__ import annotations

import streamlit as st

from frontend.components.metrics.cost_breakdown import render_cost_breakdown
from frontend.components.metrics.operations_status import render_operations_status
from frontend.components.metrics.latency_charts import render_latency_charts
from frontend.components.metrics.session_metrics_table import render_session_metrics_table
from frontend.components.metrics.token_charts import render_token_charts
from frontend.state.session_state import get_active_session_id, list_session_ids
from frontend.styles.constants import (
    CALL_CACHE_EMBEDDING,
    CALL_ESTIMATION,
    CALL_GUARDRAILS,
    CALL_MEMORY_EXTRACTION,
)
from frontend.utils.cost_utils import aggregate_call_log, cost_timeline
from frontend.utils.formatting import format_usd


def render_metrics_dashboard() -> None:
    call_log = st.session_state.get("call_log", [])
    global_cost = float(st.session_state.get("global_total_cost_usd", 0.0))

    st.markdown(f"### Coste acumulado global: **{format_usd(global_cost, 4)}**")
    render_operations_status()

    f1, f2, f3 = st.columns(3)
    with f1:
        session_filter = st.selectbox(
            "Sesión",
            options=["all", *list_session_ids()],
            format_func=lambda x: "Todas" if x == "all" else str(x)[:16],
            key="metrics_filter_session",
        )
    with f2:
        call_filter = st.selectbox(
            "Tipo de llamada",
            options=[
                "all",
                CALL_ESTIMATION,
                CALL_MEMORY_EXTRACTION,
                CALL_GUARDRAILS,
                CALL_CACHE_EMBEDDING,
            ],
            key="metrics_filter_call_type",
        )
    with f3:
        search = st.text_input("Buscar", key="metrics_search", placeholder="modelo, trace, session…")

    agg = aggregate_call_log(
        call_log,
        session_id=session_filter,
        call_type=call_filter,
    )

    active = get_active_session_id()
    if active and session_filter in ("all", active):
        rec = st.session_state.sessions_registry.get(active)
        if rec:
            st.caption(f"Coste sesión activa: {format_usd(float(rec.get('total_cost_usd', 0.0)), 4)}")

    render_cost_breakdown(agg)

    timeline = cost_timeline(agg["rows"])
    if timeline:
        st.markdown("#### Evolución temporal del coste (acumulado)")
        st.line_chart(timeline)

    c1, c2 = st.columns(2)
    with c1:
        render_token_charts(agg["rows"])
    with c2:
        render_latency_charts(agg["rows"])

    st.divider()
    st.markdown("#### Detalle de llamadas")
    render_session_metrics_table(agg["rows"], search=search)
