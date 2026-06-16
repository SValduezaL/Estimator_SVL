#!/usr/bin/env python3
"""Run ingestion offline for a catalog source (no HTTP)."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.config import get_settings
from app.foundation.persistence.database import get_sync_session_factory
from app.foundation.persistence.repositories.jobs import JobsRepository
from app.ingestion.catalog.loader import load_catalog
from app.ingestion.loaders.filesystem import FileSystemLoader
from app.ingestion.orchestrator import IngestionRejected, ingest_source
from app.ingestion.parsers.registry import default_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline ingestion for a catalog source.")
    parser.add_argument(
        "source_name",
        help="Catalog source name (must have decision=include)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Path to catalog YAML (default: settings.catalog_path)",
    )
    args = parser.parse_args()

    settings = get_settings()
    catalog_path = args.catalog or settings.catalog_path
    catalog = load_catalog(catalog_path)
    loader = FileSystemLoader(settings.ingestion_data_root)
    registry = default_registry()

    session = get_sync_session_factory()()
    try:
        repo = JobsRepository(session)
        job = repo.create(source_name=args.source_name)
        documents = ingest_source(
            catalog=catalog,
            source_name=args.source_name,
            loader=loader,
            registry=registry,
            jobs_repo=repo,
            job_id=job.job_id,
        )
    except IngestionRejected as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        session.close()

    print(f"OK job_id={job.job_id} documents={len(documents)}")
    for doc in documents[:5]:
        print(f"  - {doc.id} ({len(doc.text)} chars)")
    if len(documents) > 5:
        print(f"  ... and {len(documents) - 5} more")


if __name__ == "__main__":
    main()
