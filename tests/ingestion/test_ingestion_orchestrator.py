"""Tests for ingestion orchestrator."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.ingestion.catalog.loader import load_catalog
from app.ingestion.loaders.filesystem import FileSystemLoader
from app.ingestion.orchestrator import IngestionRejected, ingest_source
from app.ingestion.parsers.registry import default_registry


@dataclass
class FakeJob:
    job_id: uuid.UUID
    source_name: str
    status: str = "pending"
    documents_count: int = 0
    error_message: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class FakeJobsRepository:
    def __init__(self) -> None:
        self.jobs: dict[uuid.UUID, FakeJob] = {}

    def create(self, source_name: str) -> FakeJob:
        job = FakeJob(job_id=uuid.uuid4(), source_name=source_name)
        self.jobs[job.job_id] = job
        return job

    def mark_running(self, job_id: uuid.UUID) -> None:
        self.jobs[job_id].status = "running"

    def mark_completed(self, job_id: uuid.UUID, *, documents_count: int) -> None:
        job = self.jobs[job_id]
        job.status = "completed"
        job.documents_count = documents_count
        job.finished_at = datetime.now(timezone.utc)

    def mark_failed(self, job_id: uuid.UUID, *, error_message: str) -> None:
        job = self.jobs[job_id]
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = datetime.now(timezone.utc)


def test_ingest_source_budgets() -> None:
    catalog = load_catalog("data/catalog/catalog.yaml")
    loader = FileSystemLoader("data/seed")
    repo = FakeJobsRepository()
    job = repo.create("presupuestos_json")

    documents = ingest_source(
        catalog=catalog,
        source_name="presupuestos_json",
        loader=loader,
        registry=default_registry(),
        jobs_repo=repo,  # type: ignore[arg-type]
        job_id=job.job_id,
    )

    assert len(documents) == 15
    assert repo.jobs[job.job_id].status == "completed"
    assert repo.jobs[job.job_id].documents_count == 15


def test_ingest_rejects_excluded_source() -> None:
    catalog = load_catalog("data/catalog/catalog.yaml")
    loader = FileSystemLoader("data/seed")
    repo = FakeJobsRepository()
    job = repo.create("rate_card_xlsx")

    with pytest.raises(IngestionRejected, match="exclude"):
        ingest_source(
            catalog=catalog,
            source_name="rate_card_xlsx",
            loader=loader,
            registry=default_registry(),
            jobs_repo=repo,  # type: ignore[arg-type]
            job_id=job.job_id,
        )
