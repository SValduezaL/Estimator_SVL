"""Tests for ingestion HTTP API."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_catalog, get_filesystem_loader, get_parser_registry, get_sync_session
from app.foundation.persistence.repositories.jobs import Job, JobsRepository
from app.ingestion.catalog.loader import load_catalog
from app.ingestion.loaders.filesystem import FileSystemLoader
from app.ingestion.parsers.registry import default_registry
from app.main import app


class _SessionStub:
    def close(self) -> None:
        pass


@pytest.fixture
def ingestion_client(client: TestClient) -> TestClient:
    catalog = load_catalog("data/catalog/catalog.yaml")
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_filesystem_loader] = lambda: FileSystemLoader("data/seed")
    app.dependency_overrides[get_parser_registry] = lambda: default_registry()
    app.dependency_overrides[get_sync_session] = lambda: iter([_SessionStub()])
    yield client
    for key in (get_catalog, get_filesystem_loader, get_parser_registry, get_sync_session):
        app.dependency_overrides.pop(key, None)


def test_create_run_returns_202(ingestion_client: TestClient) -> None:
    job_id = uuid.uuid4()
    fake_job = Job(
        job_id=job_id,
        source_name="presupuestos_json",
        status="pending",
        documents_count=0,
        error_message=None,
        started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        finished_at=None,
    )

    with patch.object(JobsRepository, "create", return_value=fake_job):
        with patch("app.api.ingestion._run_in_background"):
            response = ingestion_client.post(
                "/api/v1/ingestion/runs",
                json={"source_name": "presupuestos_json"},
            )

    assert response.status_code == 202
    body = response.json()
    assert body["source_name"] == "presupuestos_json"
    assert body["status"] == "pending"
    assert body["job_id"] == str(job_id)


def test_create_run_unknown_source_404(ingestion_client: TestClient) -> None:
    response = ingestion_client.post(
        "/api/v1/ingestion/runs",
        json={"source_name": "does_not_exist"},
    )
    assert response.status_code == 404


def test_create_run_excluded_source_400(ingestion_client: TestClient) -> None:
    response = ingestion_client.post(
        "/api/v1/ingestion/runs",
        json={"source_name": "rate_card_xlsx"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["reason"] == "source_not_included"


def test_get_job_not_found(ingestion_client: TestClient) -> None:
    with patch.object(JobsRepository, "get", return_value=None):
        response = ingestion_client.get(f"/api/v1/ingestion/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
