"""Tests del store de sesiones en memoria."""

from __future__ import annotations

import pytest

from app.generation.conversation.exceptions import SessionNotFoundError
from app.generation.conversation.models import Message
from app.generation.conversation.store import (
    SESSIONS,
    create_session,
    delete_session,
    get_session,
    update_session,
)


def test_create_session_returns_unique_ids() -> None:
    s1 = create_session()
    s2 = create_session()
    assert s1.session_id != s2.session_id
    assert len(SESSIONS) == 2


def test_get_session_loads_existing() -> None:
    created = create_session()
    loaded = get_session(created.session_id)
    assert loaded.session_id == created.session_id
    assert loaded.history == []
    assert loaded.project_metadata.is_empty()


def test_get_session_missing_raises() -> None:
    with pytest.raises(SessionNotFoundError):
        get_session("missing-session-id")


def test_update_session_persists_changes() -> None:
    session = create_session()
    session.history.append(Message(role="user", content="Hola"))
    updated = update_session(session)
    reloaded = get_session(updated.session_id)
    assert len(reloaded.history) == 1
    assert reloaded.history[0].content == "Hola"


def test_delete_session_removes_entry() -> None:
    session = create_session()
    delete_session(session.session_id)
    with pytest.raises(SessionNotFoundError):
        get_session(session.session_id)
