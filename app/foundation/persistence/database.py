"""Async SQLAlchemy engine and session factory (S8) + sync stack for ingestion (S6)."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        resolved = settings or get_settings()
        _engine = create_async_engine(resolved.database_url, echo=False)
    return _engine


def get_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(settings),
            expire_on_commit=False,
        )
    return _session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


@lru_cache
def create_sync_engine_from_settings() -> Engine:
    return create_engine(
        get_settings().sync_database_url(),
        pool_pre_ping=True,
    )


_sync_session_factory: sessionmaker[Session] | None = None


def get_sync_session_factory() -> sessionmaker[Session]:
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=create_sync_engine_from_settings(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _sync_session_factory


def get_sync_session() -> Iterator[Session]:
    """FastAPI dependency: sync Session for ingestion jobs and PII mappings."""
    factory = get_sync_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
