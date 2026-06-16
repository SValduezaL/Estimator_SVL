"""Dependencias FastAPI reutilizables."""

from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.foundation.persistence.database import get_async_session, get_sync_session
from app.ingestion.catalog import DataCatalog, load_catalog
from app.ingestion.loaders.filesystem import FileSystemLoader
from app.ingestion.parsers.registry import ParserRegistry, default_registry
from app.domain.estimation_service import EstimationService
from app.foundation.guardrails.pipeline import create_openai_client
from app.foundation.llm.runtime_config import RuntimeModelConfig
from app.foundation.llm.wrapper import LLMWrapper
from app.generation.cag import EstimationCacheOrchestrator, build_cache_orchestrator
from app.generation.cag.exact import EstimationExactCache
from app.generation.rag.chunking.base import Chunker
from app.generation.rag.chunking.structural import JSONStructuralChunker
from app.generation.rag.chunking.strategies import (
    ContextualRetrievalChunker,
    FixedSizeChunker,
    HierarchicalChunker,
    PropositionalChunker,
    RecursiveChunker,
    SemanticChunker,
    SentenceWindowChunker,
)
from app.generation.rag.embedding.embedder import OpenAIEmbedder

_async_openai_client: Any | None = None
_async_openai_client_key: str | None = None

_orchestrator: EstimationCacheOrchestrator | None = None
_orchestrator_key: str | None = None


def _orchestrator_cache_key(settings: Settings) -> str:
    url = (settings.redis_url or "").strip()
    return (
        f"{url}|{settings.cache_ttl_seconds}|{settings.semantic_cache_enabled}|"
        f"{settings.semantic_cache_threshold}|{settings.semantic_cache_log_only}|"
        f"{settings.semantic_cache_index_name}|{settings.semantic_embedding_model}"
    )


def get_cache_orchestrator(
    settings: Settings = Depends(get_settings),
) -> EstimationCacheOrchestrator | None:
    global _orchestrator, _orchestrator_key
    url = (settings.redis_url or "").strip()
    if not url:
        return None
    key = _orchestrator_cache_key(settings)
    if _orchestrator is None or _orchestrator_key != key:
        _orchestrator = build_cache_orchestrator(settings, redis_client=None)
        _orchestrator_key = key
    return _orchestrator


def get_estimation_cache(
    orchestrator: EstimationCacheOrchestrator | None = Depends(get_cache_orchestrator),
) -> EstimationExactCache | None:
    """Compatibilidad: expone la capa exacta del orquestador."""
    if orchestrator is None:
        return None
    return orchestrator._exact


def get_llm_wrapper(
    settings: Settings = Depends(get_settings),
    orchestrator: EstimationCacheOrchestrator | None = Depends(get_cache_orchestrator),
) -> LLMWrapper:
    return LLMWrapper(settings, orchestrator=orchestrator)


def get_openai_moderation_client(
    settings: Settings = Depends(get_settings),
) -> Any | None:
    if not settings.guardrails_enabled or not settings.guardrails_moderation_enabled:
        return None
    return create_openai_client(settings)


def get_async_openai_client(
    settings: Settings = Depends(get_settings),
) -> Any | None:
    """Cliente OpenAI asíncrono para el extractor de metadata."""
    global _async_openai_client, _async_openai_client_key
    if not settings.openai_api_key:
        return None
    key = settings.openai_api_key
    if _async_openai_client is None or _async_openai_client_key != key:
        try:
            import certifi
            import httpx
            from openai import AsyncOpenAI

            ssl_context = ssl.create_default_context(cafile=certifi.where())
            http_client = httpx.AsyncClient(
                verify=ssl_context,
                timeout=httpx.Timeout(120.0, connect=15.0),
            )
            _async_openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                http_client=http_client,
            )
            _async_openai_client_key = key
        except Exception:
            _async_openai_client = None
            _async_openai_client_key = None
    return _async_openai_client


def get_estimation_service(
    settings: Settings = Depends(get_settings),
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
    orchestrator: EstimationCacheOrchestrator | None = Depends(get_cache_orchestrator),
    openai_client=Depends(get_openai_moderation_client),
    metadata_client: Any | None = Depends(get_async_openai_client),
) -> EstimationService:
    return EstimationService(
        settings=settings,
        wrapper=wrapper,
        orchestrator=orchestrator,
        openai_client=openai_client,
        metadata_client=metadata_client,
    )


_runtime_config: RuntimeModelConfig | None = None
_runtime_config_key: str | None = None


def get_runtime_config(
    settings: Settings = Depends(get_settings),
) -> RuntimeModelConfig | None:
    global _runtime_config, _runtime_config_key
    url = (settings.redis_url or "").strip()
    if not url:
        return None
    key = url
    if _runtime_config is None or _runtime_config_key != key:
        _runtime_config = RuntimeModelConfig.from_url(url, settings)
        _runtime_config_key = key
    return _runtime_config


def get_chunker() -> JSONStructuralChunker:
    return JSONStructuralChunker()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


def get_embedder(
    settings: Settings = Depends(get_settings),
) -> OpenAIEmbedder | None:
    if not settings.openai_api_key:
        return None
    return OpenAIEmbedder()


def get_fixed_size_chunker() -> FixedSizeChunker:
    return FixedSizeChunker()


def get_recursive_chunker() -> RecursiveChunker:
    return RecursiveChunker()


def get_sentence_window_chunker() -> SentenceWindowChunker:
    return SentenceWindowChunker()


def get_hierarchical_chunker() -> HierarchicalChunker:
    return HierarchicalChunker()


def get_semantic_chunker(settings: Settings = Depends(get_settings)) -> SemanticChunker:
    return SemanticChunker(api_key=settings.openai_api_key, model=settings.semantic_embedding_model)


def get_propositional_chunker(settings: Settings = Depends(get_settings)) -> PropositionalChunker:
    if not settings.openai_api_key:
        raise RuntimeError("PropositionalChunker requires OPENAI_API_KEY.")
    runtime = get_runtime_config(settings)
    model = runtime.effective("PROPOSITIONAL_CHUNKER_MODEL") if runtime else settings.llm_model
    return PropositionalChunker(api_key=settings.openai_api_key, model=model)


def get_contextual_retrieval_chunker(
    settings: Settings = Depends(get_settings),
) -> ContextualRetrievalChunker:
    if not settings.anthropic_api_key:
        raise RuntimeError("ContextualRetrievalChunker requires ANTHROPIC_API_KEY.")
    runtime = get_runtime_config(settings)
    model = runtime.effective("CONTEXTUAL_CHUNKER_MODEL") if runtime else settings.llm_model
    return ContextualRetrievalChunker(api_key=settings.anthropic_api_key, model=model)


CHUNKER_FACTORIES = {
    "structural": get_chunker,
    "fixed_size": get_fixed_size_chunker,
    "recursive": get_recursive_chunker,
    "sentence_window": get_sentence_window_chunker,
    "semantic": get_semantic_chunker,
    "propositional": get_propositional_chunker,
    "contextual_retrieval": get_contextual_retrieval_chunker,
    "hierarchical": get_hierarchical_chunker,
}
ALL_STRATEGIES = list(CHUNKER_FACTORIES)


def build_chunkers(names: list[str], settings: Settings | None = None) -> list[Chunker]:
    chunkers: list[Chunker] = []
    for name in names:
        factory = CHUNKER_FACTORIES.get(name)
        if factory is None:
            raise KeyError(name)
        if name in {"semantic", "propositional", "contextual_retrieval"} and settings is not None:
            if name == "semantic":
                chunkers.append(get_semantic_chunker(settings))
            elif name == "propositional":
                chunkers.append(get_propositional_chunker(settings))
            else:
                chunkers.append(get_contextual_retrieval_chunker(settings))
        else:
            chunkers.append(factory())
    return chunkers


@lru_cache
def get_catalog() -> DataCatalog:
    settings = get_settings()
    return load_catalog(settings.catalog_path)


@lru_cache
def get_filesystem_loader() -> FileSystemLoader:
    settings = get_settings()
    return FileSystemLoader(data_root=settings.ingestion_data_root)


@lru_cache
def get_parser_registry() -> ParserRegistry:
    return default_registry()


def build_pseudonymizer(session: Session):
    from app.ingestion.pii import ConsistentPseudonymizer, PostgresMappingStore, build_analyzer

    settings = get_settings()
    return ConsistentPseudonymizer(
        analyzer=build_analyzer(),
        mapping_store=PostgresMappingStore(session),
        salt=settings.pseudonym_hash_salt,
        faker_locale=settings.pseudonym_faker_locale,
        language="es",
    )
