#!/usr/bin/env python3
"""Ingest all budgets from data/budgets_sample.json into the vector store."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_API_BASE = os.environ.get("ESTIMATOR_API_BASE_URL", "http://localhost:8000")
CORPUS_PATH = _REPO_ROOT / "data" / "budgets_sample.json"


def main() -> None:
    budgets = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    base_url = DEFAULT_API_BASE.rstrip("/")

    with httpx.Client(timeout=120.0) as client:
        for budget in budgets:
            budget_id = budget["budget_id"]
            source_path = f"data/budgets/{budget_id}.json"
            payload = {
                "source_path": source_path,
                "document_type": "historical_budget",
                "content": budget,
            }
            response = client.post(f"{base_url}/embeddings/ingest", json=payload)
            if response.status_code == 409:
                print(f"SKIP (already ingested): {source_path}")
                continue
            response.raise_for_status()
            body = response.json()
            print(
                f"OK {source_path}: document_id={body['document_id']} "
                f"chunks={body['chunks_created']}"
            )


if __name__ == "__main__":
    main()
