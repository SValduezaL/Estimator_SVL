"""Tabla de fases."""

from __future__ import annotations

from typing import Any

import streamlit as st

_PHASE_COLUMNS = (
    "name",
    "deliverable",
    "stack",
    "hours",
    "cost_eur",
    "confidence_pct",
    "risks_notes",
)
_HEADERS = {
    "name": "Fase",
    "deliverable": "Entregable",
    "stack": "Stack",
    "hours": "Horas",
    "cost_eur": "Coste (EUR)",
    "confidence_pct": "Conf. %",
    "risks_notes": "Riesgos",
}


def phases_to_markdown(phases: list[dict[str, Any]]) -> str:
    headers = [_HEADERS.get(c, c) for c in _PHASE_COLUMNS]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in phases:
        cells: list[str] = []
        for col in _PHASE_COLUMNS:
            raw = row.get(col)
            if raw is None or raw == "":
                cells.append("—")
            elif col == "cost_eur":
                cells.append(f"{int(raw):,}".replace(",", "."))
            elif col == "stack":
                cells.append(
                    ", ".join(str(x) for x in raw)
                    if isinstance(raw, list)
                    else "—"
                )
            else:
                cells.append(str(raw).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_phases_table(phases: list[dict[str, Any]]) -> None:
    if phases:
        st.markdown(phases_to_markdown(phases))
    else:
        st.caption("Sin fases.")
