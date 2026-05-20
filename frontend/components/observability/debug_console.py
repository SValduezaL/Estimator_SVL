"""Consola de observabilidad técnica."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.components.common.empty_state import empty_state
from frontend.state.session_state import get_active_session_id, get_session_record


def render_observability_console() -> None:
    call_log = st.session_state.get("call_log", [])
    if not call_log:
        empty_state("Sin telemetría", "Realiza al menos una estimación para ver trazas.")
        return

    idx = st.selectbox(
        "Evento",
        options=list(range(len(call_log))),
        format_func=lambda i: _format_event(call_log[i], i),
        key="observability_selected_index",
    )
    row = call_log[idx]

    tabs = st.tabs(
        [
            "Resumen",
            "Request",
            "Response",
            "Caché",
            "Guardrails",
            "Memoria",
        ]
    )

    with tabs[0]:
        st.json(
            {
                k: row.get(k)
                for k in (
                    "timestamp",
                    "call_type",
                    "endpoint",
                    "model",
                    "provider",
                    "cost_usd",
                    "latency_ms",
                    "cache_hit",
                    "cache_source",
                    "semantic_similarity",
                    "request_id",
                    "session_id",
                    "prompt_version",
                    "finish_reason",
                )
                if row.get(k) is not None
            }
        )

    with tabs[1]:
        payload = row.get("request_payload")
        if payload:
            st.json(payload)
        else:
            st.caption("Sin payload almacenado.")

    with tabs[2]:
        raw = row.get("raw")
        if raw:
            st.json(raw)
        else:
            st.caption("Sin respuesta raw.")

    with tabs[3]:
        st.markdown(
            f"- **cache_hit:** `{row.get('cache_hit')}`\n"
            f"- **cache_source:** `{row.get('cache_source', '—')}`\n"
            f"- **semantic_similarity:** `{row.get('semantic_similarity', '—')}`"
        )
        st.info(
            "Umbrales y lookups semánticos dependen de `SEMANTIC_CACHE_*` en el servidor. "
            "Los hits se reflejan en métricas cuando la API los expone."
        )

    with tabs[4]:
        st.caption("Guardrails se ejecutan en servidor; detalle granular pendiente de campo `metrics.guardrails`.")
        breakdown = row.get("cost_breakdown") or {}
        if breakdown.get("guardrails"):
            st.metric("Coste guardrails (USD)", breakdown.get("guardrails"))

    with tabs[5]:
        active = get_active_session_id()
        if active:
            rec = get_session_record(active)
            if rec and rec.get("memory_traces"):
                st.json(rec["memory_traces"][-1])
            else:
                st.caption("Sin traza de extracción para esta sesión.")
        else:
            st.caption("Sin sesión activa.")


def _format_event(row: dict[str, Any], index: int) -> str:
    ts = str(row.get("timestamp", ""))[:16]
    ct = row.get("call_type", "?")
    ep = row.get("endpoint", "")
    return f"#{index + 1} {ts} · {ct} · {ep}"
