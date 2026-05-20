"""Tests de estado de sesiones (sin Streamlit runtime)."""

from __future__ import annotations

from frontend.api.metrics import infer_memory_extraction_trace
from frontend.utils.cost_utils import aggregate_call_log


def test_metadata_diff_detects_technology_change() -> None:
    before = {"mentioned_technologies": ["Rails"]}
    after = {"mentioned_technologies": ["Node.js"], "rejected_options": ["Rails"]}
    trace = infer_memory_extraction_trace(
        metadata_before=before,
        metadata_after=after,
        user_turn="Switch to Node.js",
        assistant_turn="{}",
    )
    diff = trace["diff"]
    assert "Node.js" in str(diff.get("added", {}))
    assert "Rails" in str(diff.get("removed", {})) or "Rails" in str(diff.get("added", {}))


def test_aggregate_call_log_filters_session() -> None:
    log = [
        {"session_id": "a", "call_type": "estimation", "cost_usd": 0.01, "input_tokens": 10, "output_tokens": 5, "cache_hit": True},
        {"session_id": "b", "call_type": "estimation", "cost_usd": 0.02, "input_tokens": 20, "output_tokens": 10, "cache_hit": False},
    ]
    agg = aggregate_call_log(log, session_id="a")
    assert agg["count"] == 1
    assert agg["total_cost_usd"] == 0.01
    assert agg["cache_hits"] == 1
