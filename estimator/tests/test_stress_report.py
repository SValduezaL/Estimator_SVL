"""Tests for stress REPORT.md generation."""

from __future__ import annotations

from pathlib import Path

from evals.stress.report import write_report


def test_write_report_contains_tables_and_narrative(tmp_path: Path) -> None:
    csv_path = tmp_path / "results.csv"
    csv_path.write_text(
        "run_id,scenario,attachment_size_kb,repeat,turn_index,session_id,"
        "enriched_transcript_chars,attachments_total_chars,messages_in_window,"
        "anchors_count,summary_chars,tokens_in,tokens_out,cost_usd,latency_ms,"
        "cache_hit_kind,last_resolved_tier,memory_drift_pass,memory_drift_score,"
        "latency_budget_pass,cost_budget_pass,attachment_recall_pass,estimation_cached,"
        "http_status,error_type,error_message\n"
        "abc123,growing,0,0,1,s1,100,0,2,0,0,500,50,0.01,1200,none,tier-1,1,1.0,1,1,,0,,,\n"
        "abc123,growing,0,0,2,s1,100,0,4,0,50,600,60,0.02,1500,none,tier-1,0,0.5,1,1,,0,,,\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "REPORT.md"
    text = write_report(csv_path, report_path)

    assert report_path.exists()
    assert "## Summary by scenario" in text
    assert "## Latency vs tokens_in" in text
    assert "## Memory drift score vs turn" in text
    assert "## Reading" in text
    assert "Memory drift" in text
    assert "cache_hit_kind=none" in text
