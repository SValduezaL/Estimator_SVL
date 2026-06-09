#!/usr/bin/env python3
"""Compare cosine similarity between two texts using OpenAI embeddings."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

# Repo root on sys.path when run as: python ai_service/scripts/compare.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_service.app.embedding_pipeline.embedder import OpenAIEmbedder
from ai_service.app.ssl_utils import configure_ssl_certificates


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have the same dimensionality")
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        raise ValueError("Cannot compute similarity for zero-norm vectors")
    return dot / (norm_a * norm_b)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed two texts and print cosine similarity.",
    )
    parser.add_argument("--text-a", required=True, help="First text to embed")
    parser.add_argument("--text-b", required=True, help="Second text to embed")
    args = parser.parse_args()

    configure_ssl_certificates()
    embedder = OpenAIEmbedder()

    vector_a = embedder.embed_one(args.text_a)
    vector_b = embedder.embed_one(args.text_b)
    similarity = cosine_similarity(vector_a, vector_b)

    print(f"Text A: {args.text_a}")
    print(f"Text B: {args.text_b}")
    print(f"Cosine similarity: {similarity:.4f}")


if __name__ == "__main__":
    main()
