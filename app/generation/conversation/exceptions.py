"""Excepciones del subsistema de memoria conversacional."""


class SessionNotFoundError(Exception):
    """La sesión solicitada no existe en el store en memoria."""


class SessionExpiredError(Exception):
    """La sesión superó el TTL configurado y no puede reutilizarse."""


class MetadataExtractionError(Exception):
    """Falló la actualización de metadata mediante el extractor LLM."""
