"""Session 6 ingestion subsystem.

Three conceptual layers, each in its own subpackage:

* ``catalog`` — versioned audit of data sources (what we ingest and why).
* ``loaders`` + ``parsers`` — raw bytes → list[Document] (the canonical contract).
* ``cleaning`` + ``pii`` — tabular validation and GDPR pseudonymization.

The HTTP entry point lives in ``app.api.ingestion``; the offline glue that
ties everything together lives in ``app.ingestion.orchestrator``.
"""

from app.ingestion.catalog import CatalogDecision, DataCatalog, load_catalog
from app.ingestion.documents.models import Document, DocumentMetadata
from app.ingestion.orchestrator import IngestionRejected, ingest_source

__all__ = [
    "CatalogDecision",
    "DataCatalog",
    "Document",
    "DocumentMetadata",
    "IngestionRejected",
    "ingest_source",
    "load_catalog",
]
