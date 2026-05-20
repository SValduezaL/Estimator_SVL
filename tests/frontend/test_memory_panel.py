"""Tests de diff y cards de memoria."""

from __future__ import annotations

from frontend.api.metrics import infer_memory_extraction_trace
from frontend.components.memory.metadata_diff import render_metadata_diff  # noqa: F401


def test_infer_trace_includes_turns() -> None:
    trace = infer_memory_extraction_trace(
        metadata_before={},
        metadata_after={"project_name": "CRM"},
        user_turn="Project CRM",
        assistant_turn='{"summary":"ok"}',
    )
    assert trace["metadata_after"]["project_name"] == "CRM"
    assert "project_name" in trace["diff"].get("added", {})
