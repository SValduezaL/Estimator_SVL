"""Diff visual de metadata."""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st


def render_metadata_diff(diff: dict[str, Any]) -> None:
    added = diff.get("added") or {}
    removed = diff.get("removed") or {}
    modified = diff.get("modified") or {}
    if not added and not removed and not modified:
        st.caption("Sin cambios respecto al estado anterior.")
        return

    if added:
        st.markdown("**Nuevos hechos**")
        for key, val in added.items():
            st.markdown(f"<span class='est-diff-add'>+ {escape(key)}: {escape(str(val))}</span>", unsafe_allow_html=True)
    if removed:
        st.markdown("**Hechos retirados**")
        for key, val in removed.items():
            st.markdown(f"<span class='est-diff-remove'>− {escape(key)}: {escape(str(val))}</span>", unsafe_allow_html=True)
    if modified:
        st.markdown("**Modificados**")
        for key, change in modified.items():
            if isinstance(change, dict):
                st.markdown(
                    f"~ **{escape(key)}**: `{escape(str(change.get('from')))}` → `{escape(str(change.get('to')))}`"
                )
