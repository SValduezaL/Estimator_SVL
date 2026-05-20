"""Fixtures compartidos para tests de memoria conversacional."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.memory.store import clear_all_sessions


@pytest.fixture(autouse=True)
def _isolated_session_store() -> Iterator[None]:
    clear_all_sessions()
    yield
    clear_all_sessions()
