"""Tabla detallada de métricas."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.utils.formatting import format_timestamp, format_usd


def _row_to_display(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": format_timestamp(row.get("timestamp")),
        "endpoint": row.get("endpoint", "—"),
        "call_type": row.get("call_type", "—"),
        "model": row.get("model", "—"),
        "input_tokens": row.get("input_tokens", 0),
        "output_tokens": row.get("output_tokens", 0),
        "total_tokens": row.get("total_tokens", 0),
        "cost_usd": format_usd(float(row.get("cost_usd", 0.0)), 4),
        "latency_ms": row.get("latency_ms", 0),
        "cache_hit": row.get("cache_hit"),
        "session_id": (row.get("session_id") or "—")[:12],
        "request_id": (row.get("request_id") or "—")[:12],
    }


def render_session_metrics_table(
    rows: list[dict[str, Any]],
    *,
    search: str = "",
) -> None:
    filtered = rows
    if search:
        q = search.lower()
        filtered = [
            r
            for r in rows
            if q in str(r.get("model", "")).lower()
            or q in str(r.get("endpoint", "")).lower()
            or q in str(r.get("request_id", "")).lower()
            or q in str(r.get("session_id", "")).lower()
        ]

    if not filtered:
        st.caption("No hay filas que coincidan con el filtro.")
        return

    display = [_row_to_display(r) for r in reversed(filtered)]
    st.dataframe(display, use_container_width=True, hide_index=True)
