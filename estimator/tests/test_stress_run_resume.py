"""Incremental CSV + --resume behaviour for the stress runner."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.sessions.models import ProjectMetadata
from evals.stress.run import IncrementalCsvWriter, StressRunConfig, TurnMatrixKey, run_stress
from tests.conftest import make_canned_result


@pytest.mark.usefixtures("conversational_client")
def test_incremental_csv_flushes_each_row(
    conversational_client,
    fake_wrapper,
    tmp_path: Path,
) -> None:
    fake_wrapper.add_turn(
        result=make_canned_result(),
        metadata=ProjectMetadata(project_name="Nimbus"),
    )
    csv_path = tmp_path / "partial.csv"
    config = StressRunConfig(
        scenarios=["growing"],
        attachment_sizes=[0],
        repeats=1,
        max_turns=1,
        latency_budget_ms=60_000,
        cost_budget_usd=0.50,
        output=csv_path,
        report=None,
        http_base=None,
    )
    run_stress(config)

    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["turn_index"] == "1"


@pytest.mark.usefixtures("conversational_client")
def test_resume_skips_completed_matrix_cells(
    conversational_client,
    fake_wrapper,
    tmp_path: Path,
) -> None:
    for _ in range(4):
        fake_wrapper.add_turn(
            result=make_canned_result(),
            metadata=ProjectMetadata(project_name="Nimbus"),
        )

    csv_path = tmp_path / "resume.csv"
    base = StressRunConfig(
        scenarios=["growing"],
        attachment_sizes=[0],
        repeats=1,
        max_turns=2,
        latency_budget_ms=60_000,
        cost_budget_usd=0.50,
        output=csv_path,
        report=None,
        http_base=None,
    )
    first = run_stress(base)
    assert len(first) == 2

    # Only one new LLM turn pair should run on resume (turn 2 already on disk).
    fake_wrapper.chat_calls.clear()
    resumed = run_stress(
        StressRunConfig(
            scenarios=base.scenarios,
            attachment_sizes=base.attachment_sizes,
            repeats=base.repeats,
            max_turns=base.max_turns,
            latency_budget_ms=base.latency_budget_ms,
            cost_budget_usd=base.cost_budget_usd,
            output=base.output,
            report=base.report,
            http_base=base.http_base,
            resume=True,
        )
    )
    assert len(resumed) == 0
    assert len(fake_wrapper.chat_calls) == 0

    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2


def test_incremental_writer_resume_loads_keys(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    writer = IncrementalCsvWriter(path, resume=False)
    writer.append(
        {
            "run_id": "abc",
            "scenario": "growing",
            "attachment_size_kb": 0,
            "repeat": 0,
            "turn_index": 1,
            "session_id": "s1",
            "enriched_transcript_chars": 0,
            "attachments_total_chars": 0,
            "messages_in_window": 0,
            "anchors_count": 0,
            "summary_chars": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "cache_hit_kind": "none",
            "last_resolved_tier": None,
            "memory_drift_pass": 1,
            "memory_drift_score": 1.0,
            "latency_budget_pass": 1,
            "cost_budget_pass": 1,
            "attachment_recall_pass": "",
            "estimation_cached": 0,
            "http_status": "",
            "error_type": "",
            "error_message": "",
        }
    )
    writer.close()

    writer2 = IncrementalCsvWriter(path, resume=True)
    assert writer2.is_done(
        TurnMatrixKey(scenario="growing", attachment_size_kb=0, repeat=0, turn_index=1)
    )
    writer2.close()
