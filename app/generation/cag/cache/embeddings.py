"""Proveedores de embeddings desacoplados."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Protocol

import structlog

from app.cache.exceptions import EmbeddingError
from app.cache.telemetry import log_cache_event
from app.config import Settings

log = structlog.get_logger(__name__)


class EmbeddingProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vector: list[float]
    latency_ms: int
    provider: str
    model: str


class OpenAIEmbeddingProvider:
    """Embeddings vía API OpenAI."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        return self.embed_with_metadata(text).vector

    def embed_with_metadata(self, text: str) -> EmbeddingResult:
        from openai import OpenAI

        t0 = time.perf_counter()
        try:
            client = OpenAI(api_key=self._api_key)
            kwargs: dict = {"model": self._model, "input": text}
            if self._dimensions:
                kwargs["dimensions"] = self._dimensions
            response = client.embeddings.create(**kwargs)
            vector = list(response.data[0].embedding)
        except Exception as exc:
            log_cache_event(
                "semantic_cache_embedding_failed",
                error_type=type(exc).__name__,
                error_message=str(exc)[:200],
                provider=self.provider_name,
                embedding_model=self.model_name,
            )
            raise EmbeddingError(str(exc)) from exc

        latency_ms = int((time.perf_counter() - t0) * 1000)
        return EmbeddingResult(
            vector=vector,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self.model_name,
        )


class FakeEmbeddingProvider:
    """Embedding determinista para tests (hash → vector unitario)."""

    def __init__(self, *, dimensions: int = 1536, model: str = "fake-embed") -> None:
        self._dimensions = dimensions
        self._model = model

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        return self.embed_with_metadata(text).vector

    def embed_with_metadata(self, text: str) -> EmbeddingResult:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [((digest[i % len(digest)] / 255.0) * 2.0 - 1.0) for i in range(self._dimensions)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        vector = [x / norm for x in raw]
        return EmbeddingResult(
            vector=vector,
            latency_ms=0,
            provider=self.provider_name,
            model=self.model_name,
        )


def build_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    if not settings.semantic_cache_enabled:
        return None
    provider = (settings.semantic_embedding_provider or "openai").strip().lower()
    if provider == "fake":
        return FakeEmbeddingProvider(
            dimensions=int(settings.semantic_embedding_dimensions),
            model=settings.semantic_embedding_model,
        )
    if provider == "openai":
        key = settings.openai_api_key
        if not key:
            log.warning(
                "semantic_cache_embedding_provider_unconfigured",
                log_category="technical",
                reason="missing_openai_api_key",
            )
            return None
        return OpenAIEmbeddingProvider(
            api_key=key,
            model=settings.semantic_embedding_model,
            dimensions=int(settings.semantic_embedding_dimensions),
        )
    log.warning(
        "semantic_cache_embedding_provider_unknown",
        log_category="technical",
        provider=provider,
    )
    return None
