"""Composición de contexto híbrido para el LLM principal."""

from __future__ import annotations

from app.memory.models import Session


def compose_memory_context(session: Session) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if session.running_summary and session.running_summary.text.strip():
        out.append(
            {
                "role": "user",
                "content": (
                    "[Running summary of earlier conversation]\n"
                    + session.running_summary.text
                ),
            }
        )
    active_anchors = [a for a in session.anchors if a.status == "active"]
    if active_anchors:
        anchor_lines = "\n".join(f"- {a.fact}" for a in active_anchors)
        out.append(
            {
                "role": "user",
                "content": f"[Anchors]\n{anchor_lines}",
            }
        )
    out.extend(
        {"role": m.role, "content": m.content}
        for m in session.history
        if m.role in ("user", "assistant")
    )
    return out
