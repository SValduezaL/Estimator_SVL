"""Orquestación de historial, ventana deslizante e integración con estimación."""

from __future__ import annotations

from typing import Any

import structlog

from app.memory.constants import MAX_HISTORY_TURNS
from app.memory.exceptions import MetadataExtractionError
from app.memory.extractor import update_metadata_llm
from app.memory.models import Message, ProjectMetadata, Session
from app.memory.store import update_session
from app.schemas.estimation_output import EstimationResult

log = structlog.get_logger(__name__)


def apply_sliding_window(
    history: list[Message],
    max_turns: int = MAX_HISTORY_TURNS,
) -> list[Message]:
    """Conserva los últimos N turnos (user + assistant), en orden cronológico."""
    turns: list[list[Message]] = []
    current: list[Message] = []

    for msg in history:
        if msg.role == "user":
            if current:
                turns.append(current)
            current = [msg]
        elif msg.role == "assistant":
            if current and current[-1].role == "user":
                current.append(msg)
                turns.append(current)
                current = []
            else:
                current = [msg]
        else:
            continue

    if current:
        turns.append(current)

    kept = turns[-max_turns:] if max_turns > 0 else []
    flattened: list[Message] = [m for turn in kept for m in turn]

    if len(flattened) < len(history):
        log.info(
            "history_truncated",
            log_category="business",
            previous_messages=len(history),
            kept_messages=len(flattened),
            max_turns=max_turns,
        )

    return flattened


def history_to_llm_messages(history: list[Message]) -> list[dict[str, str]]:
    """Convierte historial de sesión a mensajes para el LLM principal."""
    return [
        {"role": m.role, "content": m.content}
        for m in history
        if m.role in ("user", "assistant")
    ]


def metadata_for_prompt(metadata: ProjectMetadata) -> ProjectMetadata | None:
    """Devuelve metadata solo si tiene hechos para inyectar en el system prompt."""
    return None if metadata.is_empty() else metadata


def append_turn(
    session: Session,
    *,
    user_content: str,
    assistant_content: str,
) -> Session:
    """Añade un turno user/assistant y aplica ventana deslizante al historial."""
    session.history.extend(
        [
            Message(role="user", content=user_content),
            Message(role="assistant", content=assistant_content),
        ]
    )
    session.history = apply_sliding_window(session.history)
    return session


async def refresh_metadata_from_turn(
    session: Session,
    *,
    user_turn: str,
    assistant_turn: str,
    client: Any,
) -> tuple[Session, dict[str, Any]]:
    """Actualiza project_metadata mediante el extractor LLM."""
    previous = session.project_metadata
    updated, op_metrics = await update_metadata_llm(
        previous,
        user_turn,
        assistant_turn,
        client,
    )
    session.project_metadata = updated
    if session.project_metadata != previous:
        log.info(
            "metadata_revised",
            log_category="business",
            session_id=session.session_id,
            technologies_count=len(session.project_metadata.mentioned_technologies),
            rejected_count=len(session.project_metadata.rejected_options),
        )
    return session, op_metrics


async def persist_estimation_turn(
    session: Session,
    *,
    user_turn: str,
    result: EstimationResult,
    client: Any,
) -> tuple[Session, dict[str, Any]]:
    """Registra turno, actualiza metadata y persiste la sesión."""
    assistant_turn = result.model_dump_json()
    append_turn(session, user_content=user_turn, assistant_content=assistant_turn)
    extraction_metrics: dict[str, Any] = {
        "executed": False,
        "degraded": True,
        "cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "model": None,
        "latency_ms": None,
    }
    try:
        if client is None:
            raise MetadataExtractionError("OpenAI client is not configured")
        _, extraction_metrics = await refresh_metadata_from_turn(
            session,
            user_turn=user_turn,
            assistant_turn=assistant_turn,
            client=client,
        )
    except MetadataExtractionError as exc:
        log.warning(
            "metadata_extraction_degraded",
            log_category="business",
            session_id=session.session_id,
            error_message=str(exc),
            history_saved=True,
        )
        extraction_metrics["degraded"] = True
        extraction_metrics["error"] = str(exc)
    return update_session(session), extraction_metrics
