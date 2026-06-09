"""Orquestación de historial, ventana deslizante e integración con estimación."""

from __future__ import annotations

from typing import Any

import structlog

from app.generation.conversation.constants import MAX_HISTORY_TURNS
from app.generation.conversation.compression.anchors import update_anchors_from_turn
from app.generation.conversation.compression.compression_policy import CompressionPolicy
from app.generation.conversation.exceptions import MetadataExtractionError
from app.generation.conversation.metadata_extractor import update_metadata_llm
from app.generation.conversation.models import Message, ProjectMetadata, Session
from app.generation.conversation.compression.summary import update_running_summary_llm
from app.generation.conversation.store import update_session
from app.domain.schemas.estimation_output import EstimationResult

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


def apply_sliding_window_with_removed(
    history: list[Message],
    max_turns: int = MAX_HISTORY_TURNS,
) -> tuple[list[Message], list[Message]]:
    kept = apply_sliding_window(history, max_turns=max_turns)
    removed_count = max(0, len(history) - len(kept))
    removed = history[:removed_count]
    return kept, removed


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
    previous_history = list(session.history)
    session.history.extend(
        [
            Message(role="user", content=user_content),
            Message(role="assistant", content=assistant_content),
        ]
    )
    session.history, removed = apply_sliding_window_with_removed(session.history)
    session.__dict__["_removed_messages"] = [*previous_history[:0], *removed]
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
    summary_model: str = "gpt-4o-mini",
) -> tuple[Session, dict[str, Any], dict[str, Any]]:
    """Registra turno, actualiza metadata y persiste la sesión."""
    assistant_turn = result.model_dump_json()
    append_turn(session, user_content=user_turn, assistant_content=assistant_turn)
    update_anchors_from_turn(session, user_turn=user_turn)
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
    summary_metrics: dict[str, Any] = {
        "executed": False,
        "degraded": False,
        "cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "model": summary_model,
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

    removed = CompressionPolicy.apply(
        removed_messages=list(session.__dict__.pop("_removed_messages", [])),
        anchors=session.anchors,
    )
    session, summary_metrics = await update_running_summary_llm(
        session,
        removed_messages=removed,
        client=client,
        model=summary_model,
    )
    return update_session(session), extraction_metrics, summary_metrics
