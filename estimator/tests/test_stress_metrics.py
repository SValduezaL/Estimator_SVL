"""Unit tests for stress CAG metrics (Block 4)."""

from __future__ import annotations

import pytest

from app.sessions.models import ProjectMetadata
from evals.stress.metrics import (
    AttachmentRecallMetric,
    CostBudgetMetric,
    LatencyBudgetMetric,
    MemoryDriftMetric,
    evaluate_memory_drift,
    recall_marker_token,
)
from evals.stress.observation import SessionSnapshot, TurnObservation


# --- LatencyBudgetMetric -----------------------------------------------------


def test_latency_budget_passes_under_budget() -> None:
    metric = LatencyBudgetMetric(budget_ms=3000)
    result = metric.evaluate(TurnObservation(latency_ms=2000, cost_usd=0.01))
    assert result.passed is True
    assert result.score == 1.0
    assert result.name == "latency_budget"


def test_latency_budget_fails_over_budget() -> None:
    metric = LatencyBudgetMetric(budget_ms=3000)
    result = metric.evaluate(TurnObservation(latency_ms=4000, cost_usd=0.01))
    assert result.passed is False
    assert result.score == 0.0
    assert "exceeds" in result.details


def test_latency_budget_passes_at_exact_budget() -> None:
    metric = LatencyBudgetMetric(budget_ms=3000)
    result = metric.evaluate(TurnObservation(latency_ms=3000, cost_usd=0.0))
    assert result.passed is True
    assert result.score == 1.0


# --- CostBudgetMetric -------------------------------------------------------


def test_cost_budget_passes_under_budget() -> None:
    metric = CostBudgetMetric(budget_usd=0.10)
    result = metric.evaluate(TurnObservation(latency_ms=100, cost_usd=0.05))
    assert result.passed is True
    assert result.score == 1.0


def test_cost_budget_fails_over_budget() -> None:
    metric = CostBudgetMetric(budget_usd=0.10)
    result = metric.evaluate(TurnObservation(latency_ms=100, cost_usd=0.15))
    assert result.passed is False
    assert result.score == 0.0
    assert "exceeds" in result.details


# --- MemoryDriftMetric ------------------------------------------------------


def test_memory_drift_finds_fact_in_metadata() -> None:
    snapshot = SessionSnapshot(
        metadata=ProjectMetadata(project_name="Nimbus CRM"),
    )
    metric = MemoryDriftMetric(fact="project name: Nimbus")
    result = metric.evaluate(snapshot)
    assert result.passed is True
    assert result.score == 1.0
    assert "metadata" in result.details


def test_memory_drift_fails_on_empty_snapshot() -> None:
    metric = MemoryDriftMetric(fact="project name: Nimbus")
    result = metric.evaluate(SessionSnapshot())
    assert result.passed is False
    assert result.score == 0.0
    assert "missing" in result.details


def test_memory_drift_respects_where_channels() -> None:
    snapshot = SessionSnapshot(
        anchors=["signed NDA: budget locked at 30000 EUR"],
    )
    fact = "budget locked at 30000 EUR"
    assert MemoryDriftMetric(fact=fact, where=["anchors"]).evaluate(snapshot).passed
    assert not MemoryDriftMetric(fact=fact, where=["metadata"]).evaluate(snapshot).passed


def test_memory_drift_estimation_channel() -> None:
    snapshot = SessionSnapshot(
        estimation_summary="Final estimate for Nimbus CRM rollout.",
    )
    result = MemoryDriftMetric(
        fact="Nimbus",
        where=["estimation"],
    ).evaluate(snapshot)
    assert result.passed is True
    assert "estimation" in result.details


def test_memory_drift_rejects_empty_fact() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        MemoryDriftMetric(fact="  ")


def test_latency_budget_rejects_negative_budget() -> None:
    with pytest.raises(ValueError, match="budget_ms"):
        LatencyBudgetMetric(budget_ms=-1)


# --- AttachmentRecallMetric -------------------------------------------------


def test_attachment_recall_passes_when_marker_in_summary() -> None:
    token = recall_marker_token(
        "STRESS_RECALL_MARKER_5KB: unique-scope-token-5kb-7f3a"
    )
    metric = AttachmentRecallMetric(marker_token=token)
    result = metric.evaluate(
        "Estimate includes unique-scope-token-5kb-7f3a in scope.",
    )
    assert result.passed is True
    assert result.score == 1.0


def test_attachment_recall_fails_when_marker_missing() -> None:
    metric = AttachmentRecallMetric(marker_token="unique-scope-token-5kb-7f3a")
    result = metric.evaluate("No marker in this summary.")
    assert result.passed is False
    assert result.score == 0.0


def test_evaluate_memory_drift_aggregates_facts() -> None:
    snapshot = SessionSnapshot(
        metadata=ProjectMetadata(project_name="Nimbus CRM"),
    )
    passed, score = evaluate_memory_drift(
        snapshot,
        [(1, "project name: Nimbus"), (2, "missing fact xyz")],
    )
    assert passed is False
    assert 0.0 < score < 1.0
