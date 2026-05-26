"""Cards de project_metadata."""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from frontend.components.common.badges import badge


def render_metadata_cards(metadata: dict[str, Any]) -> None:
    if not metadata or not any(
        metadata.get(k)
        for k in (
            "project_name",
            "assumed_team_size",
            "agreed_scope",
            "mentioned_technologies",
            "explicit_constraints",
            "rejected_options",
        )
    ):
        st.info("La memoria del proyecto está vacía. Los hechos aparecerán tras conversar.")
        return

    if metadata.get("project_name"):
        st.markdown(
            f"<div class='est-card'><h4>Proyecto</h4>"
            f"<div class='est-card-body'>{escape(str(metadata['project_name']))}</div></div>",
            unsafe_allow_html=True,
        )
    if metadata.get("assumed_team_size") is not None:
        st.markdown(
            f"<div class='est-card'><h4>Equipo</h4>"
            f"<div class='est-card-body'>{metadata['assumed_team_size']} ingenieros FTE</div></div>",
            unsafe_allow_html=True,
        )
    if metadata.get("agreed_scope"):
        st.markdown(
            f"<div class='est-card'><h4>Alcance acordado</h4>"
            f"<div class='est-card-body'>{escape(str(metadata['agreed_scope']))}</div></div>",
            unsafe_allow_html=True,
        )

    techs = metadata.get("mentioned_technologies") or []
    if techs:
        badges_html = "".join(badge(t, variant="accent") for t in techs)
        st.markdown(
            f"<div class='est-card'><h4>Tecnologías</h4><div class='est-card-body'>"
            f"{badges_html}</div></div>",
            unsafe_allow_html=True,
        )

    constraints = metadata.get("explicit_constraints") or []
    if constraints:
        st.markdown("<div class='est-card'><h4>Restricciones explícitas</h4><div class='est-card-body'>", unsafe_allow_html=True)
        for c in constraints:
            st.markdown(f"<div>• {escape(str(c))}</div>", unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)

    rejected = metadata.get("rejected_options") or []
    if rejected:
        st.markdown("<div class='est-card'><h4>Opciones rechazadas</h4><div class='est-card-body'>", unsafe_allow_html=True)
        for r in rejected:
            st.markdown(
                f"<span class='est-badge est-badge--warn'>{escape(str(r))}</span> ",
                unsafe_allow_html=True,
            )
        st.markdown("</div></div>", unsafe_allow_html=True)
