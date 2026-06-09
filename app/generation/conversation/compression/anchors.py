"""Reglas deterministas para promover y revisar anclas de memoria."""

from __future__ import annotations

from datetime import datetime

from app.memory.constants import MAX_ANCHORS
from app.memory.models import AnchorItem, Session

ANCHOR_HINTS = ("must", "cannot", "debe", "no puede", "compliance", "scope", "alcance")


def _topic_from_line(line: str) -> str:
    words = [w for w in line.strip().split() if w]
    return " ".join(words[:6]) or "anchor"


def update_anchors_from_turn(session: Session, *, user_turn: str) -> Session:
    """Promueve anclas cuando detecta hechos explícitos de alto valor."""
    lines = [line.strip() for line in user_turn.splitlines() if line.strip()]
    existing_facts = {a.fact for a in session.anchors}
    for idx, line in enumerate(lines):
        lowered = line.lower()
        if not any(hint in lowered for hint in ANCHOR_HINTS):
            continue
        if line in existing_facts:
            for anchor in session.anchors:
                if anchor.fact == line:
                    anchor.last_confirmed_at = datetime.utcnow()
                    anchor.status = "active"
            continue
        session.anchors.append(
            AnchorItem(
                topic=_topic_from_line(line),
                fact=line[:500],
                source_turn_index=max(0, len(session.history) + idx),
            )
        )

    # Evicción simple por recencia: conservar anclas activas más recientes.
    if len(session.anchors) > MAX_ANCHORS:
        session.anchors = sorted(
            session.anchors,
            key=lambda a: (a.status != "active", a.last_confirmed_at),
            reverse=True,
        )[:MAX_ANCHORS]
    return session
