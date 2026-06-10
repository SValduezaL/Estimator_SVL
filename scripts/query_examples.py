#!/usr/bin/env python3
"""Run representative semantic search queries against POST /search."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_API_BASE = os.environ.get("ESTIMATOR_API_BASE_URL", "http://localhost:8000")
CONTENT_PREVIEW_CHARS = 120

QUERIES: list[tuple[str, str]] = [
    (
        "sanity_direct_match",
        "REST API development with JWT authentication for financial sector",
    ),
    (
        "semantic_reformulation",
        "secure backend service with token-based access control for banking applications",
    ),
    (
        "different_domain",
        "mobile application for restaurant reservations",
    ),
    (
        "ambiguous_query",
        "integration with external system",
    ),
    (
        "specific_technical",
        "migration from monolith to microservices architecture using Kubernetes",
    ),
]


def preview(text: str, limit: int = CONTENT_PREVIEW_CHARS) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1] + "…"


def main() -> None:
    base_url = DEFAULT_API_BASE.rstrip("/")

    with httpx.Client(timeout=60.0) as client:
        for label, query in QUERIES:
            print("=" * 80)
            print(f"Query [{label}]: {query}")
            print("-" * 80)

            response = client.post(
                f"{base_url}/search",
                json={"query": query, "k": 5},
            )
            response.raise_for_status()
            body = response.json()

            print(f"search_time_ms: {body['search_time_ms']}")
            if not body["results"]:
                print("(no results)")
                continue

            for rank, item in enumerate(body["results"], start=1):
                print(
                    f"  {rank}. chunk_id={item['chunk_id']} "
                    f"distance={item['distance']:.4f} "
                    f"chunk_type={item['chunk_type']}"
                )
                print(f"     {preview(item['content'])}")


if __name__ == "__main__":
    main()
