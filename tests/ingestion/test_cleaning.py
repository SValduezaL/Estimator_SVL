"""Tests for budget cleaning (S7 flattened schema)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.generation.rag.schemas import Budget
from app.ingestion.parsers.budget_json import budget_to_flat_record

pytest.importorskip("pandas")
pytest.importorskip("pandera")

from app.ingestion.cleaning.budget_records import clean_budget_records
from app.ingestion.cleaning.policy import validate_with_policy


def test_clean_and_validate_budget_records() -> None:
    sample_path = Path("data/seed/budgets/BUD-2024-014.json")
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    budget = Budget.model_validate(payload)
    records = [budget_to_flat_record(budget)]
    df = clean_budget_records(records)
    result = validate_with_policy(df)
    assert len(result.valid) == 1
    assert len(result.quarantined) == 0
    assert len(result.discarded) == 0
