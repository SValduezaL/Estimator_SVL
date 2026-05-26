"""Typed inputs for stress metrics (Block 4).

These shapes mirror ``turn_observed`` and session state without coupling
to the golden ``(GoldenCase, EstimationResult)`` harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.sessions.models import ProjectMetadata


class SessionInfoLike(Protocol):
    """Duck-typed session GET payload (router model or HTTP JSON dict)."""

    metadata: ProjectMetadata
    summary_text: str | None
    anchor_texts: list[str]


@dataclass(frozen=True)
class TurnObservation:
    """Per-turn LLM observability for budget metrics."""

    latency_ms: int
    cost_usd: float


class SessionSnapshot(BaseModel):
    """Session state visible after turn N (with N > k) for memory-drift checks."""

    metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)
    summary: str | None = Field(
        default=None,
        description="Cumulative conversation summary (ConversationHistory.summary).",
    )
    anchors: list[str] = Field(
        default_factory=list,
        description="Verbatim anchor message contents, in order.",
    )
    estimation_summary: str | None = Field(
        default=None,
        description="Latest actor EstimationResult.summary for this turn.",
    )


def snapshot_from_session_info(
    info: SessionInfoLike | dict[str, Any],
    *,
    estimation_summary: str | None = None,
) -> SessionSnapshot:
    """Build a drift snapshot from GET /sessions/{id} (+ optional turn summary)."""
    if isinstance(info, dict):
        metadata = ProjectMetadata.model_validate(info.get("metadata") or {})
        summary_text = info.get("summary_text")
        anchor_texts = list(info.get("anchor_texts") or [])
    else:
        metadata = info.metadata
        summary_text = info.summary_text
        anchor_texts = list(info.anchor_texts)
    return SessionSnapshot(
        metadata=metadata,
        summary=summary_text,
        anchors=anchor_texts,
        estimation_summary=estimation_summary,
    )
