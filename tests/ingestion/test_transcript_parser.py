"""Tests for TranscriptTxtParser."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.ingestion.catalog.models import (
    CatalogDecision,
    CatalogSource,
    QualityScore,
    Sensitivity,
)
from app.ingestion.loaders.filesystem import LoadedBlob
from app.ingestion.parsers.protocol import ParseContext
from app.ingestion.parsers.transcript_txt import TranscriptTxtParser


def _context() -> ParseContext:
    source = CatalogSource(
        name="transcripciones_txt",
        location="transcripts",
        format="txt",
        quality=QualityScore(completeness=4, consistency=4, actuality=4, reliability=4),
        sensitivity=Sensitivity(has_pii=True, pii_flags=["PERSON"]),
        decision=CatalogDecision.INCLUDE,
    )
    return ParseContext(
        source=source,
        source_version="test-1",
        ingested_at=datetime.now(timezone.utc),
    )


def test_transcript_tagged_mode() -> None:
    text = Path("examples/transcripts/01_clear.txt").read_text(encoding="utf-8")
    blob = LoadedBlob(relative_path="transcripts/01_clear.txt", bytes_=text.encode("utf-8"))
    docs = list(TranscriptTxtParser().parse(blob, _context()))
    assert len(docs) >= 3
    assert all(doc.metadata.extra.get("format_mode") == "tagged" for doc in docs)
    assert any("speaker" in doc.metadata.extra for doc in docs)


def test_transcript_legacy_mode() -> None:
    legacy = "Primer bloque de texto plano sin tags.\n\nSegundo bloque separado por línea en blanco."
    blob = LoadedBlob(relative_path="transcripts/legacy.txt", bytes_=legacy.encode("utf-8"))
    docs = list(TranscriptTxtParser().parse(blob, _context()))
    assert len(docs) == 2
    assert all(doc.metadata.extra.get("format_mode") == "legacy" for doc in docs)
