"""Tests for BudgetJsonParser (S7 schema)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.ingestion.catalog.models import (
    CatalogDecision,
    CatalogSource,
    QualityScore,
    Sensitivity,
)
from app.ingestion.loaders.filesystem import LoadedBlob
from app.ingestion.parsers.budget_json import BudgetJsonParser, budget_to_flat_record
from app.ingestion.parsers.protocol import ParseContext


def _context() -> ParseContext:
    source = CatalogSource(
        name="presupuestos_json",
        location="budgets",
        format="json",
        quality=QualityScore(completeness=5, consistency=5, actuality=5, reliability=5),
        sensitivity=Sensitivity(has_pii=True, pii_flags=["BUDGET_ID"]),
        decision=CatalogDecision.INCLUDE,
    )
    return ParseContext(
        source=source,
        source_version="test-1",
        ingested_at=datetime.now(timezone.utc),
    )


def test_budget_parser_renders_markdown() -> None:
    sample_path = Path("data/seed/budgets/BUD-2024-014.json")
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    blob = LoadedBlob(relative_path="budgets/BUD-2024-014.json", bytes_=json.dumps(payload).encode())
    docs = list(BudgetJsonParser().parse(blob, _context()))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.id.startswith("presupuestos_json:BUD-2024-014:")
    assert "# Presupuesto BUD-2024-014" in doc.text
    assert "## Componentes" in doc.text
    assert "OAuth 2.0" in doc.text
    assert doc.metadata.extra["budget_id"] == "BUD-2024-014"
    assert doc.metadata.extra["component_count"] == 4


def test_budget_to_flat_record() -> None:
    sample_path = Path("data/seed/budgets/BUD-2024-014.json")
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    from app.generation.rag.schemas import Budget

    budget = Budget.model_validate(payload)
    flat = budget_to_flat_record(budget)
    assert flat["budget_id"] == "BUD-2024-014"
    assert flat["client_name"] == "FintechCorp"
    assert flat["total_estimated_hours"] == 480
