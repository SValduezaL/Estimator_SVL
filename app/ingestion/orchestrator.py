"""Orchestrator: glues catalog + loader + parser into a single ingestion run."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from app.foundation.persistence.repositories.jobs import JobsRepository
from app.ingestion.catalog.models import CatalogDecision, DataCatalog
from app.ingestion.documents.models import Document
from app.ingestion.loaders.filesystem import FileSystemLoader
from app.ingestion.parsers.protocol import ParseContext
from app.ingestion.parsers.registry import ParserRegistry

log = structlog.get_logger(__name__)


class IngestionRejected(Exception):
    """The source is unknown or excluded/review — the run cannot start."""


def ingest_source(
    *,
    catalog: DataCatalog,
    source_name: str,
    loader: FileSystemLoader,
    registry: ParserRegistry,
    jobs_repo: JobsRepository,
    job_id: uuid.UUID,
) -> list[Document]:
    bound = log.bind(job_id=str(job_id), source_name=source_name)

    source = catalog.find(source_name)
    if source is None:
        raise IngestionRejected(f"source {source_name!r} not found in catalog")
    if source.decision is not CatalogDecision.INCLUDE:
        raise IngestionRejected(
            f"source {source_name!r} has decision={source.decision.value!r}; "
            f"only 'include' sources can be ingested"
        )

    jobs_repo.mark_running(job_id)
    bound.info("ingestion.started", format=source.format)

    parser = registry.get(source.format)
    context = ParseContext(
        source=source,
        source_version=catalog.version,
        ingested_at=datetime.now(timezone.utc),
    )

    documents: list[Document] = []
    try:
        for blob in loader.iter_blobs(source.location, {source.format}):
            for document in parser.parse(blob, context):
                documents.append(document)
    except Exception as exc:
        bound.error("ingestion.failed", error=str(exc))
        jobs_repo.mark_failed(job_id, error_message=str(exc))
        raise

    jobs_repo.mark_completed(job_id, documents_count=len(documents))
    bound.info("ingestion.completed", documents_count=len(documents))
    return documents
