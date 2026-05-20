"""Sidebar: gestión de sesiones."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st

from frontend.api.client import ApiError
from frontend.api.sessions import SessionClient
from frontend.components.common.stat_card import stat_card
from frontend.state.session_state import (
    archive_session,
    delete_session_local,
    get_active_session_id,
    get_session_record,
    list_session_ids,
    register_session,
    set_active_session,
    update_session_from_api,
)
from frontend.utils.formatting import format_usd, truncate


def render_session_sidebar(*, session_client: SessionClient, api_base: str) -> None:
    st.markdown("### Sesiones")
    if st.button("＋ Nueva sesión", use_container_width=True, type="primary"):
        try:
            data = session_client.create_session()
            sid = str(data["session_id"])
            register_session(sid)
            try:
                detail = session_client.get_session(sid)
                update_session_from_api(sid, detail)
            except ApiError:
                pass
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))

    st.divider()
    active = get_active_session_id()
    for sid in list_session_ids():
        rec = get_session_record(sid)
        if not rec or rec.get("archived"):
            continue
        is_active = sid == active
        preview = ""
        msgs = rec.get("messages") or []
        if msgs:
            last = msgs[-1]
            preview = truncate(str(last.get("content", "")), 60)
        label = rec.get("name", sid[:8])
        cost = float(rec.get("total_cost_usd", 0.0))
        hits = int(rec.get("cache_hits", 0))
        misses = int(rec.get("cache_misses", 0))
        btn_label = f"{'● ' if is_active else ''}{label}"

        if st.button(btn_label, key=f"sel_{sid}", use_container_width=True):
            set_active_session(sid)
            try:
                detail = session_client.get_session(sid)
                update_session_from_api(sid, detail)
            except ApiError:
                pass
            st.rerun()

        st.caption(f"{preview or 'Sin mensajes'} · {format_usd(cost, 4)} · {hits}H/{misses}M")

    if active:
        rec = get_session_record(active)
        if rec:
            st.divider()
            new_name = st.text_input("Nombre de sesión", value=rec.get("name", ""), key="session_rename")
            if new_name and new_name != rec.get("name"):
                rec["name"] = new_name
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Archivar", use_container_width=True):
                    archive_session(active)
                    st.rerun()
            with c2:
                if st.button("Eliminar local", use_container_width=True):
                    delete_session_local(active)
                    st.rerun()

    st.divider()
    st.markdown("### Resumen")
    global_cost = float(st.session_state.get("global_total_cost_usd", 0.0))
    stat_card("Coste global", format_usd(global_cost, 4))
    if active and get_session_record(active):
        r = get_session_record(active)
        stat_card("Sesión activa", format_usd(float(r.get("total_cost_usd", 0.0)), 4))
        stat_card("Mensajes", str(r.get("message_count", 0)))

    st.divider()
    st.caption("Servidor")
    st.code(f"{api_base}/api/v1", language="text")
    redis = "activa" if (os.getenv("REDIS_URL") or "").strip() else "off"
    st.markdown(f"**Caché Redis:** {redis}")
