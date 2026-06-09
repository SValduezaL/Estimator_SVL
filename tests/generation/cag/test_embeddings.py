"""Tests de proveedores de embeddings."""

from __future__ import annotations

import math

from app.generation.cag.embeddings import FakeEmbeddingProvider


def test_fake_embedding_deterministic() -> None:
    p = FakeEmbeddingProvider(dimensions=16)
    v1 = p.embed("hello world")
    v2 = p.embed("hello world")
    v3 = p.embed("different")
    assert v1 == v2
    assert v1 != v3
    norm = math.sqrt(sum(x * x for x in v1))
    assert abs(norm - 1.0) < 1e-5
