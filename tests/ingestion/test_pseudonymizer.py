"""Tests for ConsistentPseudonymizer."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

pytest.importorskip("faker")

from app.ingestion.pii.mapping_store import InMemoryMappingStore
from app.ingestion.pii.pseudonymizer import ConsistentPseudonymizer


@dataclass
class FakeResult:
    entity_type: str
    start: int
    end: int


class FakeAnalyzer:
    def analyze(self, text: str, language: str, entities: list[str] | None = None) -> list[FakeResult]:
        results: list[FakeResult] = []
        needle = "BUD-2024-014"
        start = text.find(needle)
        if start >= 0:
            results.append(FakeResult(entity_type="BUDGET_ID", start=start, end=start + len(needle)))
        return results


def test_pseudonymizer_is_consistent() -> None:
    store = InMemoryMappingStore()
    pseudo = ConsistentPseudonymizer(
        analyzer=FakeAnalyzer(),  # type: ignore[arg-type]
        mapping_store=store,
        salt="test-salt",
    )
    text = "Presupuesto BUD-2024-014 para cliente"
    first = pseudo.pseudonymize(text)
    second = pseudo.pseudonymize(text)
    assert first.pseudonymized_text == second.pseudonymized_text
    assert "BUD-2024-014" not in first.pseudonymized_text
    assert len(first.applied) == 1


def test_pseudonymizer_no_entities_unchanged() -> None:
    store = InMemoryMappingStore()
    pseudo = ConsistentPseudonymizer(
        analyzer=FakeAnalyzer(),  # type: ignore[arg-type]
        mapping_store=store,
        salt="test-salt",
    )
    result = pseudo.pseudonymize("texto sin identificadores")
    assert result.pseudonymized_text == "texto sin identificadores"
    assert result.applied == []
