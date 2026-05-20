"""Tests de TTL y expiración de sesiones."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.memory.constants import SESSION_TTL_HOURS
from app.memory.exceptions import SessionExpiredError, SessionNotFoundError
from app.memory.models import Message
from app.memory.store import (
    SESSIONS,
    cleanup_expired_sessions,
    create_session,
    get_session,
    update_session,
)


def test_expired_session_raises_and_is_removed() -> None:
    session = create_session()
    session.updated_at = datetime.utcnow() - timedelta(hours=SESSION_TTL_HOURS + 1)
    SESSIONS[session.session_id] = session

    with pytest.raises(SessionExpiredError):
        get_session(session.session_id)

    assert session.session_id not in SESSIONS


def test_active_session_within_ttl_loads() -> None:
    session = create_session()
    loaded = get_session(session.session_id)
    assert loaded.session_id == session.session_id


def test_cleanup_expired_sessions_purges_stale() -> None:
    active = create_session()
    stale = create_session()
    stale.updated_at = datetime.utcnow() - timedelta(hours=SESSION_TTL_HOURS + 2)
    SESSIONS[stale.session_id] = stale

    purged = cleanup_expired_sessions()
    assert purged == 1
    assert stale.session_id not in SESSIONS
    assert active.session_id in SESSIONS


def test_update_session_refreshes_updated_at() -> None:
    session = create_session()
    old_updated = session.updated_at
    session.history.append(Message(role="user", content="ping"))
    update_session(session)
    assert session.updated_at >= old_updated
    get_session(session.session_id)


def test_missing_session_still_not_found() -> None:
    with pytest.raises(SessionNotFoundError):
        get_session("does-not-exist")
