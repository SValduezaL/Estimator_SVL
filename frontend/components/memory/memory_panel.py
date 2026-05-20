"""Panel de memoria conversacional."""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.components.common.empty_state import empty_state
from frontend.components.memory.metadata_cards import render_metadata_cards
from frontend.components.memory.metadata_diff import render_metadata_diff
from frontend.state.session_state import get_active_session_id, get_session_record
from frontend.utils.formatting import format_timestamp


def render_memory_panel() -> None:
    active = get_active_session_id()
    if not active:
        empty_state("Sin sesión", "Selecciona o crea una sesión para inspeccionar la memoria.")
        return

    rec = get_session_record(active)
    if not rec:
        empty_state("Sesión no encontrada", "Registro local ausente.")
        return

    metadata = rec.get("metadata_current") or {}
    st.markdown("### Estado actual (`project_metadata`)")
    render_metadata_cards(metadata)

    st.divider()
    st.markdown("### Evolución de la memoria")
    history = rec.get("metadata_history") or []
    if not history:
        st.caption("Aún no hay snapshots de metadata.")
    else:
        for i, snap in enumerate(reversed(history)):
            ts = format_timestamp(snap.get("timestamp"))
            source = snap.get("source", "—")
            with st.expander(f"{ts} · {source}", expanded=(i == 0)):
                render_metadata_cards(snap.get("metadata") or {})
                diff = snap.get("diff")
                if diff:
                    render_metadata_diff(diff)

    st.divider()
    st.markdown("### Trazas de extracción LLM")
    traces = rec.get("memory_traces") or []
    if not traces:
        st.caption("Sin trazas aún.")
        return

    for i, trace in enumerate(reversed(traces)):
        ts = format_timestamp(trace.get("timestamp"))
        with st.expander(f"Extracción · {ts}", expanded=(i == 0)):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Metadata anterior**")
                st.json(trace.get("metadata_before") or {})
            with c2:
                st.markdown("**Metadata nueva**")
                st.json(trace.get("metadata_after") or {})
            st.markdown("**Diff generado**")
            render_metadata_diff(trace.get("diff") or {})
            st.markdown("**Turno USER**")
            st.code(trace.get("user_turn", ""), language="text")
            st.markdown("**Turno ASSISTANT (extractor)**")
            st.code(trace.get("assistant_turn", ""), language="text")
