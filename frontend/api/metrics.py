"""Parsing y agregación de métricas LLM desde respuestas API."""

from __future__ import annotations

from typing import Any

from frontend.styles.constants import (
    CALL_CACHE_EMBEDDING,
    CALL_ESTIMATION,
    CALL_GUARDRAILS,
    CALL_MEMORY_EXTRACTION,
)


def parse_estimation_metrics(
    response: dict[str, Any],
    *,
    latency_seconds: float | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Normaliza métricas de ``EstimationResponse`` + bloque opcional ``metrics``."""
    usage = response.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}

    base = {
        "call_type": CALL_ESTIMATION,
        "endpoint": "/api/v1/estimate",
        "model": str(response.get("model", "—")),
        "provider": str(response.get("provider", "—")),
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
        "cost_usd": float(response.get("cost_usd", 0.0)),
        "latency_ms": int(
            (latency_seconds if latency_seconds is not None else response.get("response_seconds", 0))
            * 1000
        ),
        "cache_hit": bool(response.get("cache_hit", False)),
        "finish_reason": str(response.get("finish_reason", "—")),
        "prompt_version": str(response.get("prompt_version", "—")),
        "request_id": request_id,
        "session_id": session_id,
        "raw": dict(response),
    }

    extended = response.get("metrics")
    if isinstance(extended, dict):
        costs = extended.get("costs") or {}
        if isinstance(costs, dict):
            base["cost_breakdown"] = {
                CALL_ESTIMATION: float(costs.get("estimation_usd", base["cost_usd"])),
                CALL_MEMORY_EXTRACTION: float(costs.get("memory_extraction_usd", 0.0)),
                CALL_GUARDRAILS: float(costs.get("guardrails_usd", 0.0)),
                CALL_CACHE_EMBEDDING: float(costs.get("cache_embedding_usd", 0.0)),
            }
        tokens = extended.get("tokens")
        if isinstance(tokens, dict):
            base["tokens_breakdown"] = tokens
        latency = extended.get("latency")
        if isinstance(latency, dict):
            base["latency_breakdown"] = latency
    else:
        base["cost_breakdown"] = {
            CALL_ESTIMATION: base["cost_usd"],
            CALL_MEMORY_EXTRACTION: 0.0,
            CALL_GUARDRAILS: 0.0,
            CALL_CACHE_EMBEDDING: 0.0,
        }

    cache_source = response.get("cache_source") or extended.get("cache_source") if isinstance(extended, dict) else None
    if cache_source:
        base["cache_source"] = str(cache_source)
    similarity = response.get("semantic_similarity")
    if similarity is None and isinstance(extended, dict):
        similarity = extended.get("semantic_similarity")
    if similarity is not None:
        base["semantic_similarity"] = float(similarity)

    return base


def infer_memory_extraction_trace(
    *,
    metadata_before: dict[str, Any],
    metadata_after: dict[str, Any],
    user_turn: str,
    assistant_turn: str,
) -> dict[str, Any]:
    """Construye traza de extracción a partir del diff servidor (sin heurísticas de contenido)."""
    return {
        "call_type": CALL_MEMORY_EXTRACTION,
        "metadata_before": metadata_before,
        "metadata_after": metadata_after,
        "user_turn": user_turn,
        "assistant_turn": assistant_turn[:4000] + ("…" if len(assistant_turn) > 4000 else ""),
        "diff": _metadata_diff(metadata_before, metadata_after),
    }

def _metadata_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {"added": {}, "removed": {}, "modified": {}}
    keys = (
        "project_name",
        "assumed_team_size",
        "agreed_scope",
        "mentioned_technologies",
        "explicit_constraints",
        "rejected_options",
    )
    for key in keys:
        b_val = before.get(key)
        a_val = after.get(key)
        if b_val == a_val:
            continue
        if key in ("mentioned_technologies", "explicit_constraints", "rejected_options"):
            b_set = set(b_val or [])
            a_set = set(a_val or [])
            added = sorted(a_set - b_set)
            removed = sorted(b_set - a_set)
            if added:
                changes["added"][key] = added
            if removed:
                changes["removed"][key] = removed
        else:
            if b_val is None and a_val is not None:
                changes["added"][key] = a_val
            elif b_val is not None and a_val is None:
                changes["removed"][key] = b_val
            else:
                changes["modified"][key] = {"from": b_val, "to": a_val}
    return changes
