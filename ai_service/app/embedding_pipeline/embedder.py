"""OpenAI embedding client for the ingest pipeline."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import TypeVar

import structlog
from openai import OpenAI, RateLimitError

from ai_service.app.config import Settings, get_settings
from ai_service.app.embedding_pipeline.schemas import Chunk, EmbeddedChunk

log = structlog.get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
# Price per million input tokens (text-embedding-3-small); update when OpenAI changes pricing.
EMBEDDING_COST_USD_PER_MILLION_TOKENS = 0.02
BATCH_SIZE = 100
RATE_LIMIT_RETRY_DELAYS_SECONDS = (1, 2, 4)

T = TypeVar("T")


def estimate_embedding_cost_usd(total_tokens: int) -> float:
    """Estimated USD cost for embedding input tokens."""
    return total_tokens * EMBEDDING_COST_USD_PER_MILLION_TOKENS / 1_000_000


class OpenAIEmbedder:
    """Embeds chunk text via OpenAI ``text-embedding-3-small`` (default 1536 dims)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = EMBEDDING_MODEL,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        self._api_key = api_key if api_key is not None else resolved_settings.openai_api_key
        self._model = model
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def embed_one(self, text: str) -> list[float]:
        vectors = self._create_embeddings([text])
        return vectors[0]

    def embed_many(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        if not chunks:
            return []

        embedded: list[EmbeddedChunk] = []
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            vectors = self._embed_batch(batch)
            embedded.extend(
                EmbeddedChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    metadata=chunk.metadata,
                    token_count=chunk.token_count,
                    embedding=vector,
                )
                for chunk, vector in zip(batch, vectors, strict=True)
            )
        return embedded

    def _embed_batch(self, batch: Sequence[Chunk]) -> list[list[float]]:
        texts = [chunk.text for chunk in batch]
        tokens_in_batch = sum(chunk.token_count for chunk in batch)
        t0 = time.perf_counter()

        vectors = self._create_embeddings(texts)

        latency_ms = int((time.perf_counter() - t0) * 1000)
        log.info(
            "embedding_batch_processed",
            log_category="technical",
            chunks_count=len(batch),
            tokens_in_batch=tokens_in_batch,
            latency_ms=latency_ms,
            model=self._model,
        )
        return vectors

    def _create_embeddings(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()

        def call_api() -> list[list[float]]:
            response = client.embeddings.create(model=self._model, input=texts)
            ordered = sorted(response.data, key=lambda item: item.index)
            return [list(item.embedding) for item in ordered]

        return self._call_with_rate_limit_retries(call_api)

    def _call_with_rate_limit_retries(self, fn: Callable[[], T]) -> T:
        last_error: RateLimitError | None = None
        for attempt in range(len(RATE_LIMIT_RETRY_DELAYS_SECONDS) + 1):
            try:
                return fn()
            except RateLimitError as exc:
                last_error = exc
                if attempt >= len(RATE_LIMIT_RETRY_DELAYS_SECONDS):
                    break
                delay = RATE_LIMIT_RETRY_DELAYS_SECONDS[attempt]
                log.warning(
                    "embedding_rate_limited_retry",
                    log_category="technical",
                    attempt=attempt + 1,
                    delay_seconds=delay,
                    model=self._model,
                )
                time.sleep(delay)
        assert last_error is not None
        raise last_error
