"""Store en memoria de proceso para sesiones conversacionales."""

from __future__ import annotations

from datetime import datetime, timedelta

import structlog

from app.generation.conversation.constants import SESSION_TTL_HOURS
from app.generation.conversation.exceptions import SessionExpiredError, SessionNotFoundError
from app.generation.conversation.models import Session

log = structlog.get_logger(__name__)

SESSIONS: dict[str, Session] = {}


def _ttl_delta() -> timedelta:
    return timedelta(hours=SESSION_TTL_HOURS)


def _is_expired(session: Session, *, now: datetime | None = None) -> bool:
    reference = now or datetime.utcnow()
    return reference - session.updated_at > _ttl_delta()


def create_session() -> Session:
    """Crea una sesión vacía y la registra en el store."""
    session = Session()
    SESSIONS[session.session_id] = session
    log.info(
        "session_created",
        log_category="business",
        session_id=session.session_id,
        history_size=0,
        metadata_empty=session.project_metadata.is_empty(),
    )
    return session


def get_session(session_id: str) -> Session:
    """Obtiene una sesión activa o lanza si no existe o expiró."""
    session = SESSIONS.get(session_id)
    if session is None:
        log.warning(
            "session_not_found",
            log_category="business",
            session_id=session_id,
        )
        raise SessionNotFoundError(f"Session {session_id!r} not found")

    if _is_expired(session):
        log.info(
            "session_expired",
            log_category="business",
            session_id=session_id,
            updated_at=session.updated_at.isoformat(),
            ttl_hours=SESSION_TTL_HOURS,
        )
        SESSIONS.pop(session_id, None)
        raise SessionExpiredError(f"Session {session_id!r} has expired")

    log.info(
        "session_loaded",
        log_category="business",
        session_id=session_id,
        history_size=len(session.history),
        metadata_fields_populated=sum(
            1
            for flag in (
                bool(session.project_metadata.project_name),
                session.project_metadata.assumed_team_size is not None,
                bool(session.project_metadata.mentioned_technologies),
                bool(session.project_metadata.agreed_scope),
                bool(session.project_metadata.explicit_constraints),
                bool(session.project_metadata.rejected_options),
            )
            if flag
        ),
    )
    return session


def update_session(session: Session) -> Session:
    """Persiste la sesión actualizada en el store."""
    session.updated_at = datetime.utcnow()
    SESSIONS[session.session_id] = session
    log.info(
        "session_updated",
        log_category="business",
        session_id=session.session_id,
        history_size=len(session.history),
        metadata_empty=session.project_metadata.is_empty(),
    )
    return session


def delete_session(session_id: str) -> None:
    """Elimina una sesión del store (idempotente)."""
    removed = SESSIONS.pop(session_id, None)
    if removed is not None:
        log.info(
            "session_deleted",
            log_category="business",
            session_id=session_id,
        )


def cleanup_expired_sessions(*, now: datetime | None = None) -> int:
    """Elimina sesiones expiradas. Devuelve el número de sesiones purgadas."""
    reference = now or datetime.utcnow()
    expired_ids = [
        sid
        for sid, session in list(SESSIONS.items())
        if reference - session.updated_at > _ttl_delta()
    ]
    for sid in expired_ids:
        SESSIONS.pop(sid, None)
        log.info(
            "session_expired_cleanup",
            log_category="business",
            session_id=sid,
            ttl_hours=SESSION_TTL_HOURS,
        )
    if expired_ids:
        log.info(
            "session_cleanup_completed",
            log_category="business",
            purged_count=len(expired_ids),
            remaining_sessions=len(SESSIONS),
        )
    return len(expired_ids)


def clear_all_sessions() -> None:
    """Vacía el store (tests)."""
    SESSIONS.clear()
