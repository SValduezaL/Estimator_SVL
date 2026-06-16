"""Fixtures for ingestion tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from app.ingestion.catalog.models import CatalogDecision, DataCatalog
from app.ingestion.catalog.models import CatalogSource, QualityScore, Sensitivity

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample_catalog_source() -> CatalogSource:
    return CatalogSource(
        name="presupuestos_json",
        description="test budgets",
        location="budgets",
        format="json",
        quality=QualityScore(completeness=5, consistency=5, actuality=5, reliability=5),
        sensitivity=Sensitivity(has_pii=True, pii_flags=["BUDGET_ID"]),
        decision=CatalogDecision.INCLUDE,
    )


@pytest.fixture
def sample_data_catalog(sample_catalog_source: CatalogSource) -> DataCatalog:
    return DataCatalog(version="test-1", sources=[sample_catalog_source])


@pytest.fixture
def seed_root() -> Path:
    return REPO_ROOT / "data" / "seed"


@pytest.fixture
def catalog_yaml_path(tmp_path: Path, sample_catalog_source: CatalogSource) -> Path:
    payload = {
        "version": "test-1",
        "sources": [sample_catalog_source.model_dump(mode="json")],
    }
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.dump(payload, allow_unicode=True), encoding="utf-8")
    return path
