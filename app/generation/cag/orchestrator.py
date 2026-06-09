"""Orquestación de caché exacta y semántica (lookup/store)."""

from __future__ import annotations

from typing import Any

import structlog

from app.generation.cag.embeddings import EmbeddingProvider
from app.generation.cag.exact import EstimationExactCache
from app.generation.cag.keys import bucket_for_context
from app.generation.cag.policies import (
    is_result_cacheable,
    should_read_cache,
    should_write_exact,
    should_write_semantic,
)
from app.generation.cag.semantic import EstimationSemanticCache
from app.generation.cag.telemetry import cache_timer, log_cache_event
from app.generation.cag.types import (
    CachedPayload,
    CacheContext,
    CacheLookupResult,
    CacheSource,
)
from app.config import Settings
from app.foundation.prompts.registry import PromptBundle
from app.domain.schemas.estimation_request import EstimationRequest

log = structlog.get_logger(__name__)


def build_cache_context(
    *,
    request: EstimationRequest,
    bundle: PromptBundle,
    schema_version: str,
    model: str,
    max_tokens: int,
    thinking_budget: int | None,
    skip_cache: bool = False,
) -> CacheContext:
    return CacheContext(
        request=request,
        bundle=bundle,
        schema_version=schema_version,
        model=model,
        max_tokens=max_tokens,
        thinking_budget=thinking_budget,
        skip_cache=skip_cache,
    )


class EstimationCacheOrchestrator:
    """Coordina exact v2 → semantic → store con embedding reutilizable."""

    def __init__(
        self,
        *,
        settings: Settings,
        exact: EstimationExactCache,
        semantic: EstimationSemanticCache | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._settings = settings
        self._exact = exact
        self._semantic = semantic
        self._embeddings = embedding_provider

    def lookup(self, ctx: CacheContext) -> CacheLookupResult:
        if not should_read_cache(ctx, self._settings):
            return CacheLookupResult(hit=False)

        bucket = bucket_for_context(ctx).as_tag()
        embedding: list[float] | None = None

        with cache_timer("cache_lookup", bucket=bucket):
            exact_result = self._exact.lookup(ctx)
            if exact_result.hit:
                log_cache_event(
                    "cache_hit",
                    cache_source=CacheSource.EXACT.value,
                    bucket=bucket,
                )
                return exact_result

            if self._semantic is None:
                log_cache_event("semantic_cache_miss", bucket=bucket, reason="disabled")
                return CacheLookupResult(hit=False)

            if self._embeddings is not None:
                try:
                    if hasattr(self._embeddings, "embed_with_metadata"):
                        emb = self._embeddings.embed_with_metadata(ctx.description)  # type: ignore[attr-defined]
                        embedding = emb.vector
                    else:
                        embedding = self._embeddings.embed(ctx.description)
                except Exception:
                    return CacheLookupResult(hit=False)

            sem = self._semantic.lookup(ctx, embedding=embedding)
            if sem.hit and sem.payload is not None:
                return CacheLookupResult(
                    hit=True,
                    source=CacheSource.SEMANTIC,
                    payload=sem.payload,
                    similarity=sem.similarity,
                    embedding=embedding,
                )
            if sem.log_only_would_hit:
                return CacheLookupResult(
                    hit=False,
                    similarity=sem.similarity,
                    embedding=embedding,
                    log_only_would_hit=True,
                )
            return CacheLookupResult(hit=False, embedding=embedding)

    def store(
        self,
        ctx: CacheContext,
        payload: CachedPayload,
        *,
        embedding: list[float] | None = None,
        cacheable: bool = True,
    ) -> None:
        if not cacheable or not is_result_cacheable(payload.result):
            log_cache_event(
                "cache_store_skipped",
                reason="not_cacheable",
                bucket=bucket_for_context(ctx).as_tag(),
            )
            return
        if ctx.skip_cache:
            return

        if should_write_exact(ctx, self._settings):
            self._exact.store(ctx, payload)

        if should_write_semantic(ctx, self._settings) and self._semantic is not None:
            self._semantic.store(ctx, payload, embedding=embedding)


def build_cache_orchestrator(
    settings: Settings,
    redis_client: Any,
) -> EstimationCacheOrchestrator | None:
    url = (settings.redis_url or "").strip()
    if not url:
        return None

    from app.generation.cag.embeddings import build_embedding_provider
    from app.generation.cag.redis import create_redis_client

    if redis_client is None:
        redis_client = create_redis_client(url)

    exact = EstimationExactCache(redis_client, ttl=int(settings.cache_ttl_seconds))
    embedding_provider = build_embedding_provider(settings)
    semantic: EstimationSemanticCache | None = None
    if settings.semantic_cache_enabled and embedding_provider is not None:
        try:
            semantic = EstimationSemanticCache(
                redis_client=redis_client,
                embedding_provider=embedding_provider,
                settings=settings,
            )
        except Exception as exc:
            log.warning(
                "semantic_cache_init_failed",
                log_category="technical",
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
            )
            semantic = None

    return EstimationCacheOrchestrator(
        settings=settings,
        exact=exact,
        semantic=semantic,
        embedding_provider=embedding_provider,
    )
