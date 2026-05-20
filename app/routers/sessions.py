"""Router HTTP para sesiones conversacionales."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException

from app.memory.exceptions import SessionExpiredError, SessionNotFoundError
from app.memory.store import create_session, get_session
from app.schemas.session import SessionCreateResponse, SessionDetailResponse

router = APIRouter(prefix="/api/v1", tags=["sessions"])
log = structlog.get_logger(__name__)


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_conversation_session() -> SessionCreateResponse:
    """Crea una sesión vacía (reset explícito: nueva sesión sin memoria previa)."""
    session = create_session()
    log.info(
        "session_endpoint_created",
        log_category="business",
        session_id=session.session_id,
    )
    return SessionCreateResponse(session_id=session.session_id)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def read_conversation_session(session_id: str) -> SessionDetailResponse:
    """Devuelve historial y metadata de proyecto de la sesión."""
    try:
        session = get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SessionExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    return SessionDetailResponse(
        session_id=session.session_id,
        history=session.history,
        project_metadata=session.project_metadata,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
