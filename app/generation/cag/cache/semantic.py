"""Caché semántica con Redis Stack + redisvl."""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np
import structlog

from app.cache.embeddings import EmbeddingProvider
from app.cache.exceptions import EmbeddingError
from app.cache.keys import bucket_for_context
from app.cache.telemetry import increment_cache_metric, log_cache_event
from app.cache.types import (
    CachedPayload,
    CacheContext,
    SemanticLookupResult,
    SemanticMatch,
)
from app.config import Settings

log = structlog.get_logger(__name__)


def vector_to_bytes(vector: list[float]) -> bytes:
    """RediSearch almacena vectores como float32 bytes."""
    return np.array(vector, dtype=np.float32).tobytes()


def _index_schema(
    *,
    index_name: str,
    prefix: str,
    dimensions: int,
) -> dict[str, Any]:
    return {
        "index": {
            "name": index_name,
            "prefix": prefix,
            "storage_type": "hash",
        },
        "fields": [
            {"name": "bucket", "type": "tag"},
            {"name": "result_json", "type": "text"},
            {
                "name": "embedding",
                "type": "vector",
                "attrs": {
                    "dims": dimensions,
                    "distance_metric": "cosine",
                    "algorithm": "flat",
                },
            },
        ],
    }


class EstimationSemanticCache:
    """Búsqueda por similitud vectorial (cosine) filtrada por bucket."""

    def __init__(
        self,
        *,
        redis_client: Any,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
        index_name: str | None = None,
    ) -> None:
        from redisvl.index import SearchIndex

        self.redis_client = redis_client
        self._embeddings = embedding_provider
        self._settings = settings
        self.threshold = float(settings.semantic_cache_threshold)
        self.ttl = settings.resolved_semantic_cache_ttl()
        self.log_only = bool(settings.semantic_cache_log_only)
        self.max_results = int(settings.semantic_cache_max_results)

        idx_name = index_name or settings.semantic_cache_index_name
        prefix = settings.semantic_cache_key_prefix
        dims = int(settings.semantic_embedding_dimensions)

        schema = _index_schema(
            index_name=idx_name,
            prefix=prefix,
            dimensions=dims,
        )
        self.index = SearchIndex.from_dict(schema)
        self.index.set_client(redis_client)
        try:
            self.index.create(overwrite=False)
            log_cache_event(
                "semantic_cache_bucket_created",
                index_name=idx_name,
                prefix=prefix,
            )
        except Exception as exc:  # noqa: BLE001 — índice ya existe
            log.debug(
                "semantic_index_create_skipped",
                log_category="technical",
                error=str(exc)[:120],
            )

    def _embed_vector(
        self, ctx: CacheContext, embedding: list[float] | None
    ) -> list[float] | None:
        if embedding is not None:
            return embedding
        try:
            if hasattr(self._embeddings, "embed_with_metadata"):
                emb = self._embeddings.embed_with_metadata(ctx.description)  # type: ignore[attr-defined]
                log_cache_event(
                    "semantic_cache_lookup",
                    bucket=bucket_for_context(ctx).as_tag(),
                    embedding_provider=emb.provider,
                    embedding_model=emb.model,
                    embedding_latency_ms=emb.latency_ms,
                    phase="embed",
                )
                return emb.vector
            return self._embeddings.embed(ctx.description)
        except EmbeddingError:
            increment_cache_metric("semantic_cache", "embedding_failed")
            return None

    def lookup(
        self,
        ctx: CacheContext,
        *,
        embedding: list[float] | None = None,
    ) -> SemanticLookupResult:
        from redisvl.query import VectorQuery
        from redisvl.query.filter import Tag

        bucket = bucket_for_context(ctx).as_tag()
        t0 = time.perf_counter()

        vector = self._embed_vector(ctx, embedding)
        if vector is None:
            return SemanticLookupResult(hit=False)

        try:
            query = VectorQuery(
                vector=vector_to_bytes(vector),
                vector_field_name="embedding",
                return_fields=["result_json", "bucket"],
                num_results=max(1, self.max_results),
                return_score=True,
                filter_expression=Tag("bucket") == bucket,
            )
            results = self.index.query(query)
        except Exception as exc:
            log_cache_event(
                "semantic_cache_lookup",
                bucket=bucket,
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
            )
            increment_cache_metric("semantic_cache", "query_failed")
            return SemanticLookupResult(hit=False)

        latency_ms = int((time.perf_counter() - t0) * 1000)

        if not results:
            log_cache_event(
                "semantic_cache_miss",
                bucket=bucket,
                reason="empty_index",
                latency_ms=latency_ms,
            )
            increment_cache_metric("semantic_cache", "miss")
            return SemanticLookupResult(hit=False)

        top_matches: list[SemanticMatch] = []
        for row in results:
            distance = float(row.get("vector_distance", 1.0))
            similarity = round(1.0 - distance, 4)
            top_matches.append(
                SemanticMatch(
                    similarity=similarity,
                    result_json=str(row.get("result_json", "")),
                )
            )

        best = results[0]
        distance = float(best.get("vector_distance", 1.0))
        similarity = 1.0 - distance
        rounded_sim = round(similarity, 4)

        log_cache_event(
            "semantic_cache_lookup",
            bucket=bucket,
            similarity=rounded_sim,
            threshold=self.threshold,
            latency_ms=latency_ms,
            top_matches=[m.similarity for m in top_matches],
            embedding_provider=self._embeddings.provider_name,
            embedding_model=self._embeddings.model_name,
        )

        if similarity < self.threshold:
            log_cache_event(
                "semantic_cache_similarity_below_threshold",
                bucket=bucket,
                similarity=rounded_sim,
                threshold=self.threshold,
                latency_ms=latency_ms,
            )
            increment_cache_metric("semantic_cache", "below_threshold")
            return SemanticLookupResult(
                hit=False,
                similarity=rounded_sim,
                top_matches=tuple(top_matches),
            )

        if self.log_only:
            log_cache_event(
                "semantic_cache_hit_log_only",
                bucket=bucket,
                similarity=rounded_sim,
                threshold=self.threshold,
            )
            increment_cache_metric("semantic_cache", "log_only_hit")
            return SemanticLookupResult(
                hit=False,
                similarity=rounded_sim,
                top_matches=tuple(top_matches),
                log_only_would_hit=True,
            )

        try:
            raw_json = best["result_json"]
            data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            payload = CachedPayload.from_redis_dict(data)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            log_cache_event(
                "semantic_cache_miss",
                bucket=bucket,
                reason="corrupt_entry",
                error_type=type(exc).__name__,
            )
            increment_cache_metric("semantic_cache", "corrupt")
            return SemanticLookupResult(hit=False)

        log_cache_event(
            "semantic_cache_hit",
            bucket=bucket,
            similarity=rounded_sim,
            threshold=self.threshold,
            latency_ms=latency_ms,
        )
        increment_cache_metric("semantic_cache", "hit")
        return SemanticLookupResult(
            hit=True,
            payload=payload,
            similarity=rounded_sim,
            top_matches=tuple(top_matches),
        )

    def store(
        self,
        ctx: CacheContext,
        payload: CachedPayload,
        *,
        embedding: list[float] | None = None,
    ) -> None:
        bucket = bucket_for_context(ctx).as_tag()
        vector = self._embed_vector(ctx, embedding)
        if vector is None:
            return

        result_json = json.dumps(payload.to_redis_dict())
        rows = [
            {
                "bucket": bucket,
                "result_json": result_json,
                "embedding": vector_to_bytes(vector),
            }
        ]
        try:
            self.index.load(rows, ttl=self.ttl)
            log_cache_event(
                "semantic_cache_store",
                bucket=bucket,
                ttl=self.ttl,
                embedding_provider=self._embeddings.provider_name,
            )
            increment_cache_metric("semantic_cache", "stored")
        except Exception as exc:
            log_cache_event(
                "semantic_cache_store_failed",
                bucket=bucket,
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
            )
            increment_cache_metric("semantic_cache", "store_failed")
