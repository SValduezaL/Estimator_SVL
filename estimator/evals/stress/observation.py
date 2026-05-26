"""Typed inputs for stress metrics (Block 4).

These shapes mirror ``turn_observed`` and session state without coupling
to the golden ``(GoldenCase, EstimationResult)`` harness.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.sessions.models import ProjectMetadata


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
