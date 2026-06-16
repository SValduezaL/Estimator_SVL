"""Tests for catalog models."""

from __future__ import annotations

import pytest

from app.ingestion.catalog.loader import load_catalog
from app.ingestion.catalog.models import CatalogDecision, DataCatalog


def test_load_repo_catalog() -> None:
    catalog = load_catalog("data/catalog/catalog.yaml")
    assert catalog.version == "1.0.0"
    included = {s.name for s in catalog.included_sources()}
    assert "presupuestos_json" in included
    assert "transcripciones_txt" in included
    assert "rate_card_xlsx" not in included


def test_exclude_requires_reason() -> None:
    with pytest.raises(ValueError, match="decision_reason"):
        DataCatalog.model_validate(
            {
                "version": "1",
                "sources": [
                    {
                        "name": "bad_source",
                        "location": "x",
                        "format": "json",
                        "quality": {
                            "completeness": 1,
                            "consistency": 1,
                            "actuality": 1,
                            "reliability": 1,
                        },
                        "sensitivity": {"has_pii": False},
                        "decision": "exclude",
                    }
                ],
            }
        )


def test_duplicate_source_names_rejected() -> None:
    catalog_path = "data/catalog/catalog.yaml"
    catalog = load_catalog(catalog_path)
    names = [s.name for s in catalog.sources]
    assert len(names) == len(set(names))


def test_review_source_not_included() -> None:
    catalog = load_catalog("data/catalog/catalog.yaml")
    rate = catalog.find("rate_card_xlsx")
    assert rate is not None
    assert rate.decision is CatalogDecision.EXCLUDE
