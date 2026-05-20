"""Estado de sesiones conversacionales en Streamlit."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import streamlit as st

from frontend.api.metrics import infer_memory_extraction_trace, parse_estimation_metrics
from frontend.styles.constants import CALL_MEMORY_EXTRACTION

log = logging.getLogger("estimator.frontend.session")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_app_state() -> None:
    if "frontend_initialized" not in st.session_state:
        st.session_state.frontend_initialized = True
        st.session_state.sessions_registry: dict[str, dict[str, Any]] = {}
        st.session_state.active_session_id: str | None = None
        st.session_state.call_log: list[dict[str, Any]] = []
        st.session_state.global_total_cost_usd = 0.0
        st.session_state.last_api_error: dict[str, Any] | None = None
        log.info("frontend_state_initialized")


def list_session_ids() -> list[str]:
    registry: dict[str, dict[str, Any]] = st.session_state.get("sessions_registry", {})
    return sorted(
        registry.keys(),
        key=lambda sid: registry[sid].get("updated_at", ""),
        reverse=True,
    )


def get_session_record(session_id: str) -> dict[str, Any] | None:
    return st.session_state.sessions_registry.get(session_id)


def get_active_session_id() -> str | None:
    return st.session_state.get("active_session_id")


def set_active_session(session_id: str) -> None:
    if session_id not in st.session_state.sessions_registry:
        return
    st.session_state.active_session_id = session_id
    log.info("active_session_changed", extra={"session_id": session_id})


def register_session(
    session_id: str,
    *,
    name: str | None = None,
) -> dict[str, Any]:
    registry: dict[str, dict[str, Any]] = st.session_state.sessions_registry
    now = _now_iso()
    if session_id not in registry:
        registry[session_id] = {
            "session_id": session_id,
            "name": name or f"Sesión {session_id[:8]}",
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "metadata_current": {},
            "metadata_history": [],
            "memory_traces": [],
            "total_cost_usd": 0.0,
            "message_count": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "archived": False,
        }
        log.info("session_registered", extra={"session_id": session_id})
    st.session_state.active_session_id = session_id
    return registry[session_id]


def archive_session(session_id: str) -> None:
    rec = get_session_record(session_id)
    if rec:
        rec["archived"] = True
        if st.session_state.active_session_id == session_id:
            others = [s for s in list_session_ids() if s != session_id and not get_session_record(s).get("archived")]
            st.session_state.active_session_id = others[0] if others else None


def delete_session_local(session_id: str) -> None:
    st.session_state.sessions_registry.pop(session_id, None)
    if st.session_state.active_session_id == session_id:
        remaining = list_session_ids()
        st.session_state.active_session_id = remaining[0] if remaining else None


def update_session_from_api(session_id: str, api_session: dict[str, Any]) -> None:
    rec = register_session(session_id)
    rec["updated_at"] = api_session.get("updated_at", _now_iso())
    if isinstance(api_session.get("created_at"), str):
        rec["created_at"] = api_session["created_at"]
    metadata = api_session.get("project_metadata") or {}
    if isinstance(metadata, dict):
        prev = deepcopy(rec.get("metadata_current") or {})
        rec["metadata_current"] = metadata
        if metadata != prev:
            rec["metadata_history"].append(
                {
                    "timestamp": _now_iso(),
                    "metadata": deepcopy(metadata),
                    "source": "api_sync",
                }
            )
    history = api_session.get("history") or []
    if isinstance(history, list):
        rec["server_history_len"] = len(history)


def append_chat_turn(
    session_id: str,
    *,
    user_content: str,
    assistant_content: str,
    estimation_response: dict[str, Any],
    metrics_row: dict[str, Any],
    request_id: str | None,
    metadata_before: dict[str, Any],
    metadata_after: dict[str, Any],
    latency_seconds: float,
) -> None:
    rec = register_session(session_id)
    turn_id = str(uuid4())
    ts = _now_iso()

    user_msg = {
        "id": f"{turn_id}-user",
        "role": "user",
        "content": user_content,
        "timestamp": ts,
        "metrics": None,
    }
    assistant_msg = {
        "id": f"{turn_id}-assistant",
        "role": "assistant",
        "content": assistant_content,
        "timestamp": ts,
        "metrics": metrics_row,
        "result": estimation_response.get("result"),
        "raw_response": estimation_response,
        "request_id": request_id,
    }
    rec["messages"].extend([user_msg, assistant_msg])
    rec["message_count"] = len(rec["messages"])
    rec["updated_at"] = ts

    cost = float(metrics_row.get("cost_usd", 0.0))
    rec["total_cost_usd"] += cost
    st.session_state.global_total_cost_usd = float(st.session_state.get("global_total_cost_usd", 0.0)) + cost

    if metrics_row.get("cache_hit"):
        rec["cache_hits"] += 1
    else:
        rec["cache_misses"] += 1

    trace = infer_memory_extraction_trace(
        metadata_before=metadata_before,
        metadata_after=metadata_after,
        user_turn=user_content,
        assistant_turn=assistant_content,
    )
    trace["timestamp"] = ts
    trace["request_id"] = request_id
    rec["memory_traces"].append(trace)

    log_entry = {
        **metrics_row,
        "timestamp": ts,
        "turn_id": turn_id,
    }
    st.session_state.call_log.append(log_entry)

    if metadata_before != metadata_after:
        rec["metadata_history"].append(
            {
                "timestamp": ts,
                "metadata": deepcopy(metadata_after),
                "source": "memory_extraction",
                "diff": trace.get("diff"),
            }
        )

    extraction_cost = (metrics_row.get("cost_breakdown") or {}).get(CALL_MEMORY_EXTRACTION, 0.0)
    if extraction_cost > 0:
        st.session_state.call_log.append(
            {
                "call_type": CALL_MEMORY_EXTRACTION,
                "endpoint": "internal/memory_extractor",
                "cost_usd": extraction_cost,
                "timestamp": ts,
                "session_id": session_id,
                "request_id": request_id,
            }
        )


def record_estimation_call(
    *,
    session_id: str,
    payload: dict[str, Any],
    response: dict[str, Any],
    latency_seconds: float,
    request_id: str | None,
    metadata_before: dict[str, Any],
    metadata_after: dict[str, Any],
) -> None:
    metrics_row = parse_estimation_metrics(
        response,
        latency_seconds=latency_seconds,
        request_id=request_id,
        session_id=session_id,
    )
    metrics_row["timestamp"] = _now_iso()
    metrics_row["request_payload"] = deepcopy(payload)

    result = response.get("result") or {}
    assistant_content = (
        result.get("summary", "")
        if isinstance(result, dict)
        else str(result)
    )

    append_chat_turn(
        session_id,
        user_content=str(payload.get("description", "")),
        assistant_content=assistant_content,
        estimation_response=response,
        metrics_row=metrics_row,
        request_id=request_id,
        metadata_before=metadata_before,
        metadata_after=metadata_after,
        latency_seconds=latency_seconds,
    )
    update_session_from_api(session_id, {"project_metadata": metadata_after, "updated_at": _now_iso()})


def set_api_error(error: Any) -> None:
    st.session_state.last_api_error = {
        "message": str(error),
        "status_code": getattr(error, "status_code", None),
        "detail": getattr(error, "detail", None),
        "request_id": getattr(error, "request_id", None),
        "timestamp": _now_iso(),
    }


def clear_api_error() -> None:
    st.session_state.last_api_error = None
