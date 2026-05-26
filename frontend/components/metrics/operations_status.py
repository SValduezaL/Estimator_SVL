"""Panel de estado de operaciones (última estimación)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.state.session_state import get_active_session_id, get_session_record
from frontend.styles.constants import (
    CALL_CACHE_EMBEDDING,
    CALL_ESTIMATION,
    CALL_GUARDRAILS,
    CALL_MEMORY_EXTRACTION,
)
from frontend.utils.formatting import format_usd


def _badge(label: str, variant: str = "") -> str:
    cls = f"est-badge est-badge--{variant}" if variant else "est-badge"
    return f"<span class='{cls}'>{label}</span>"


def render_operations_status() -> None:
    sid = get_active_session_id()
    if not sid:
        return
    rec = get_session_record(sid)
    if not rec:
        return
    ops: dict[str, Any] | None = rec.get("last_operations")
    if not isinstance(ops, dict):
        st.caption("Sin telemetría de operaciones en la última llamada.")
        return

    costs = ops.get("costs") or {}
    if not isinstance(costs, dict):
        costs = {}

    mem = ops.get("memory_extraction") or {}
    if not isinstance(mem, dict):
        mem = {}

    lines = [
        f"<strong>{CALL_ESTIMATION}</strong>: "
        f"{format_usd(float(costs.get('estimation_usd', 0.0)), 4)}",
        (
            f"<strong>{CALL_MEMORY_EXTRACTION}</strong>: "
            f"{format_usd(float(costs.get('memory_extraction_usd', 0.0)), 4)} — "
            + (
                _badge("ejecutado", "ok")
                if ops.get("memory_extraction_executed")
                else _badge("no ejecutado", "warn")
            )
            + (
                " " + _badge("degradado", "warn")
                if ops.get("memory_extraction_degraded")
                else ""
            )
            + (
                f" · {int(mem.get('total_tokens', 0))} tok"
                if ops.get("memory_extraction_executed")
                else ""
            )
        ),
        (
            f"<strong>{CALL_GUARDRAILS}</strong>: "
            f"{format_usd(float(costs.get('guardrails_usd', 0.0)), 4)} — "
            + (
                _badge("activado", "accent")
                if ops.get("guardrails_enabled")
                else _badge("desactivado", "warn")
            )
            + (
                " " + _badge("moderación ejecutada", "ok")
                if ops.get("guardrails_moderation_executed")
                else " " + _badge("sin moderación API", "")
            )
        ),
        (
            f"<strong>{CALL_CACHE_EMBEDDING}</strong>: "
            f"{format_usd(float(costs.get('cache_embedding_usd', 0.0)), 4)} — "
            + (
                _badge("caché semántica ON", "accent")
                if ops.get("semantic_cache_enabled")
                else _badge("caché semántica OFF", "warn")
            )
            + (
                " " + _badge("lookup", "ok")
                if ops.get("cache_lookup_performed")
                else ""
            )
            + (
                " " + _badge("embedding", "ok")
                if ops.get("cache_embedding_computed")
                else ""
            )
            + (
                " " + _badge("cache hit", "cache-hit")
                if ops.get("cache_hit")
                else (
                    " " + _badge("cache miss", "cache-miss")
                    if ops.get("cache_lookup_performed")
                    else ""
                )
            )
        ),
    ]

    st.markdown(
        "<div class='est-ops-panel'><h4 style='margin:0 0 0.5rem 0'>Última estimación — operaciones</h4><ul>"
        + "".join(f"<li>{line}</li>" for line in lines)
        + "</ul></div>",
        unsafe_allow_html=True,
    )
