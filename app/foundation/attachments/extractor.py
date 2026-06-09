"""Extracción local de texto para adjuntos PDF y DOCX."""

from __future__ import annotations

import io
from pathlib import PurePosixPath

import structlog

log = structlog.get_logger(__name__)

SUPPORTED_ATTACHMENT_EXTENSIONS = {".pdf", ".docx"}


class AttachmentExtractionError(Exception):
    """Fallo al extraer texto de un adjunto."""

    def __init__(self, filename: str, message: str) -> None:
        super().__init__(message)
        self.filename = filename
        self.message = message


class UnsupportedAttachmentError(AttachmentExtractionError):
    """Adjunto con extensión no soportada."""


def _extension(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()


def _extract_pdf(content: bytes) -> str:
    chunks: list[str] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                log.warning("pdf_page_extract_failed", error=str(exc)[:200])
                text = ""
            if text.strip():
                chunks.append(text)
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf_extract_pypdf_failed", error=str(exc)[:200])

    if chunks:
        return "\n\n".join(chunks)

    # Fallback para PDFs complejos donde pypdf no devuelve texto util.
    try:
        import fitz

        doc = fitz.open(stream=content, filetype="pdf")
        blocks: list[str] = []
        for page in doc:
            text = page.get_text("text") or ""
            if text.strip():
                blocks.append(text)
        return "\n\n".join(blocks)
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf_extract_pymupdf_failed", error=str(exc)[:200])
        return ""


def _extract_docx(content: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(content))
    paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    return "\n".join(paragraphs)


def extract_text(*, filename: str, content: bytes, max_chars: int) -> str:
    """Extrae texto de un adjunto y lo trunca a ``max_chars``."""
    ext = _extension(filename)
    if ext not in SUPPORTED_ATTACHMENT_EXTENSIONS:
        raise UnsupportedAttachmentError(
            filename=filename,
            message=f"Unsupported attachment extension {ext!r}",
        )

    try:
        if ext == ".pdf":
            text = _extract_pdf(content)
        else:
            text = _extract_docx(content)
    except AttachmentExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AttachmentExtractionError(
            filename=filename,
            message=f"Failed to extract text from {filename}: {exc}",
        ) from exc

    text = text.strip()
    if not text:
        return ""

    if len(text) > max_chars:
        log.info(
            "attachment_text_truncated",
            filename=filename,
            original_chars=len(text),
            kept_chars=max_chars,
        )
        text = text[:max_chars]
    return text


def enrich_transcript(*, transcript: str, attachments: list[tuple[str, str]]) -> str:
    """Concatena la transcripción original y el texto extraído de adjuntos."""
    if not attachments:
        return transcript

    parts = [transcript.strip()]
    for filename, text in attachments:
        if not text:
            continue
        parts.append(
            f"--- attachment: {filename} ---\n{text}\n--- end attachment ---",
        )
    return "\n\n".join(parts)
