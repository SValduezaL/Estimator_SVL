"""Smoke test for the stress runner (in-process, FakeLLMWrapper)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.sessions.models import ProjectMetadata
from evals.stress.run import StressRunConfig, run_stress
from tests.conftest import make_canned_result


@pytest.mark.usefixtures("conversational_client")
def test_stress_run_smoke_two_turns(
    conversational_client,
    fake_wrapper,
    tmp_path: Path,
) -> None:
    fake_wrapper.add_turn(
        result=make_canned_result(),
        metadata=ProjectMetadata(project_name="Nimbus CRM"),
    )
    fake_wrapper.add_turn(
        result=make_canned_result(total_cost_eur=30_000),
        metadata=ProjectMetadata(
            project_name="Nimbus CRM",
            agreed_scope="OAuth2 and RBAC for enterprise authentication",
        ),
    )

    csv_path = tmp_path / "results.csv"
    config = StressRunConfig(
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
    rows = run_stress(config)

    assert len(rows) == 2
    assert rows[0]["turn_index"] == 1
    assert rows[1]["turn_index"] == 2

    with csv_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        csv_rows = list(reader)
    assert len(csv_rows) == 2
    # Actor + metadata extractor per turn.
    assert csv_rows[0]["latency_ms"] == "2"
    assert csv_rows[0]["cost_usd"] == "0.0002"
    assert csv_rows[0]["tokens_in"] == "200"
    assert csv_rows[0]["memory_drift_pass"] == "1"
