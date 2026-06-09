"""Utilidades de extracción de adjuntos."""

from app.foundation.attachments.extractor import (
    AttachmentExtractionError,
    SUPPORTED_ATTACHMENT_EXTENSIONS,
    UnsupportedAttachmentError,
    enrich_transcript,
    extract_text,
)

__all__ = [
    "AttachmentExtractionError",
    "SUPPORTED_ATTACHMENT_EXTENSIONS",
    "UnsupportedAttachmentError",
    "enrich_transcript",
    "extract_text",
]
