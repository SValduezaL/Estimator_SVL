from __future__ import annotations

import pytest

from app.foundation.attachments.extractor import (
    AttachmentExtractionError,
    UnsupportedAttachmentError,
    enrich_transcript,
    extract_text,
)


def test_extract_text_unsupported_extension() -> None:
    with pytest.raises(UnsupportedAttachmentError):
        extract_text(filename="notes.txt", content=b"hola", max_chars=200)


def test_extract_text_pdf_uses_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.foundation.attachments import extractor

    monkeypatch.setattr(extractor, "_extract_pdf", lambda _content: "a" * 30)
    text = extract_text(filename="scope.pdf", content=b"%PDF", max_chars=10)
    assert text == "a" * 10


def test_extract_text_docx_wraps_parser_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.foundation.attachments import extractor

    def boom(_content: bytes) -> str:
        raise RuntimeError("broken file")

    monkeypatch.setattr(extractor, "_extract_docx", boom)
    with pytest.raises(AttachmentExtractionError):
        extract_text(filename="scope.docx", content=b"PK", max_chars=100)


def test_enrich_transcript_includes_attachment_sections() -> None:
    output = enrich_transcript(
        transcript="Necesito estimar un CRM",
        attachments=[("scope.pdf", "Detalle funcional"), ("empty.docx", "")],
    )
    assert "Necesito estimar un CRM" in output
    assert "--- attachment: scope.pdf ---" in output
    assert "Detalle funcional" in output
    assert "empty.docx" not in output
