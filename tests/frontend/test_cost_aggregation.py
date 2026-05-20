"""Tests de agregación de costes."""

from __future__ import annotations

import pytest

from frontend.utils.cost_utils import aggregate_call_log, cost_timeline


def test_cost_timeline_accumulates() -> None:
    log = [
        {"timestamp": "2026-05-20T10:00:00", "cost_usd": 0.01},
        {"timestamp": "2026-05-20T10:05:00", "cost_usd": 0.02},
    ]
    series = cost_timeline(log)
    assert len(series) == 2
    assert list(series.values())[-1] == pytest.approx(0.03, rel=1e-6)


def test_cost_by_type_from_breakdown() -> None:
    row = {
        "call_type": "estimation",
        "cost_usd": 0.05,
        "cost_breakdown": {"estimation": 0.04, "memory_extraction": 0.01},
        "input_tokens": 1,
        "output_tokens": 1,
        "cache_hit": False,
    }
    agg = aggregate_call_log([row])
    assert agg["cost_by_type"]["estimation"] == pytest.approx(0.04)
    assert agg["cost_by_type"]["memory_extraction"] == pytest.approx(0.01)
