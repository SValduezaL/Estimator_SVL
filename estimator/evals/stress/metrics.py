"""Deterministic stress metrics for CAG evaluation (Block 4).

Budget metrics consume :class:`~evals.stress.observation.TurnObservation`.
Memory drift consumes :class:`~evals.stress.observation.SessionSnapshot`.

All return :class:`~evals.metrics.MetricResult` from the golden harness.
Matching is exact substring, case-insensitive — no embeddings or LLM judges.
"""

from __future__ import annotations

from typing import Literal

from evals.metrics import MetricResult
from evals.stress.observation import SessionSnapshot, TurnObservation

WhereChannel = Literal["summary", "anchors", "metadata", "estimation"]

_DEFAULT_WHERE: tuple[WhereChannel, ...] = ("summary", "anchors", "metadata")
_VALID_CHANNELS: frozenset[str] = frozenset((*_DEFAULT_WHERE, "estimation"))


def _metadata_haystack(metadata) -> str:
    """Serialize metadata so scenario facts like ``project name: Nimbus`` match."""
    parts: list[str] = []
    if metadata.project_name:
        parts.append(f"project name: {metadata.project_name}")
    if metadata.agreed_scope:
        parts.append(metadata.agreed_scope)
    if metadata.mentioned_technologies:
        parts.extend(metadata.mentioned_technologies)
    if metadata.assumed_team_size is not None:
        parts.append(f"team size: {metadata.assumed_team_size}")
    return " ".join(parts)


def build_haystacks(snapshot: SessionSnapshot) -> dict[str, str]:
    """Map each searchable channel to a single lowercase-ready text blob."""
    return {
        "metadata": _metadata_haystack(snapshot.metadata),
        "summary": snapshot.summary or "",
        "anchors": "\n".join(snapshot.anchors),
        "estimation": snapshot.estimation_summary or "",
    }


class LatencyBudgetMetric:
    """1.0 if ``latency_ms <= budget_ms``; 0.0 otherwise."""

    name = "latency_budget"

    def __init__(self, budget_ms: int) -> None:
        if budget_ms < 0:
            raise ValueError("budget_ms must be >= 0")
        self.budget_ms = budget_ms

    def evaluate(self, observation: TurnObservation) -> MetricResult:
        passed = observation.latency_ms <= self.budget_ms
        if passed:
            details = (
                f"latency {observation.latency_ms}ms within budget {self.budget_ms}ms"
            )
        else:
            details = (
                f"latency {observation.latency_ms}ms exceeds budget {self.budget_ms}ms"
            )
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            details=details,
        )


class CostBudgetMetric:
    """1.0 if ``cost_usd <= budget_usd``; 0.0 otherwise."""

    name = "cost_budget"

    def __init__(self, budget_usd: float) -> None:
        if budget_usd < 0:
            raise ValueError("budget_usd must be >= 0")
        self.budget_usd = budget_usd

    def evaluate(self, observation: TurnObservation) -> MetricResult:
        passed = observation.cost_usd <= self.budget_usd
        if passed:
            details = (
                f"cost ${observation.cost_usd:.6f} within budget ${self.budget_usd:.6f}"
            )
        else:
            details = (
                f"cost ${observation.cost_usd:.6f} exceeds budget ${self.budget_usd:.6f}"
            )
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            details=details,
        )


class MemoryDriftMetric:
    """1.0 if ``fact`` appears in any selected snapshot channel; 0.0 otherwise.

    Default channels: ``summary``, ``anchors``, ``metadata``. Pass ``estimation``
    in ``where`` to also search the latest ``estimation_summary`` field.
    """

    name = "memory_drift"

    def __init__(
        self,
        fact: str,
        where: list[str] | None = None,
    ) -> None:
        self.fact = fact.strip()
        if not self.fact:
            raise ValueError("fact must be non-empty")
        channels = tuple(where) if where is not None else _DEFAULT_WHERE
        unknown = set(channels) - _VALID_CHANNELS
        if unknown:
            raise ValueError(f"unknown where channels: {sorted(unknown)}")
        self.where: tuple[str, ...] = channels

    def evaluate(self, snapshot: SessionSnapshot) -> MetricResult:
        haystacks = build_haystacks(snapshot)
        needle = self.fact.lower()

        found_in: list[str] = []
        for channel in self.where:
            text = haystacks.get(channel, "")
            if needle in text.lower():
                found_in.append(channel)

        passed = bool(found_in)
        if passed:
            details = f"found in {', '.join(found_in)}"
        else:
            details = f"missing from {', '.join(self.where)}"
        return MetricResult(
            name=self.name,
            score=1.0 if passed else 0.0,
            passed=passed,
            details=details,
        )
