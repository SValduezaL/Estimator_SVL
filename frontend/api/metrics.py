"""Parsing y agregación de métricas LLM desde respuestas API."""

from __future__ import annotations

from typing import Any

from frontend.styles.constants import (
    CALL_CACHE_EMBEDDING,
    CALL_ESTIMATION,
    CALL_GUARDRAILS,
    CALL_MEMORY_EXTRACTION,
    CALL_SUMMARY_COMPRESSION,
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

    operations = response.get("operations")
    if isinstance(operations, dict):
        costs = operations.get("costs") or {}
        if isinstance(costs, dict):
            base["cost_breakdown"] = {
                CALL_ESTIMATION: float(costs.get("estimation_usd", base["cost_usd"])),
                CALL_MEMORY_EXTRACTION: float(costs.get("memory_extraction_usd", 0.0)),
                CALL_SUMMARY_COMPRESSION: float(costs.get("summary_compression_usd", 0.0)),
                CALL_GUARDRAILS: float(costs.get("guardrails_usd", 0.0)),
                CALL_CACHE_EMBEDDING: float(costs.get("cache_embedding_usd", 0.0)),
            }
        base["operations"] = operations
    else:
        extended = response.get("metrics")
        if isinstance(extended, dict):
            costs = extended.get("costs") or {}
            if isinstance(costs, dict):
                base["cost_breakdown"] = {
                    CALL_ESTIMATION: float(costs.get("estimation_usd", base["cost_usd"])),
                    CALL_MEMORY_EXTRACTION: float(costs.get("memory_extraction_usd", 0.0)),
                CALL_SUMMARY_COMPRESSION: float(costs.get("summary_compression_usd", 0.0)),
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
                CALL_SUMMARY_COMPRESSION: 0.0,
                CALL_GUARDRAILS: 0.0,
                CALL_CACHE_EMBEDDING: 0.0,
            }

    extended = response.get("metrics")
    cache_source = response.get("cache_source")
    if cache_source is None and isinstance(operations, dict):
        cache_source = operations.get("cache_source")
    if cache_source is None and isinstance(extended, dict):
        cache_source = extended.get("cache_source")
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


def total_cost_from_response(response: dict[str, Any]) -> float:
    """Suma costes de todas las operaciones cuando la API expone ``operations``."""
    operations = response.get("operations")
    if isinstance(operations, dict):
        costs = operations.get("costs") or {}
        if isinstance(costs, dict):
            return round(
                sum(
                    float(costs.get(key, 0.0))
                    for key in (
                        "estimation_usd",
                        "memory_extraction_usd",
                        "summary_compression_usd",
                        "guardrails_usd",
                        "cache_embedding_usd",
                    )
                ),
                8,
            )
    return float(response.get("cost_usd", 0.0))


def build_operation_call_log_entries(
    response: dict[str, Any],
    *,
    timestamp: str,
    session_id: str | None,
    request_id: str | None,
    turn_id: str | None = None,
) -> list[dict[str, Any]]:
    """Filas adicionales del call_log (memoria, guardrails, embedding) desde ``operations``."""
    operations = response.get("operations")
    if not isinstance(operations, dict):
        return []

    costs = operations.get("costs") or {}
    if not isinstance(costs, dict):
        costs = {}

    mem_usage = operations.get("memory_extraction") or {}
    if not isinstance(mem_usage, dict):
        mem_usage = {}

    entries: list[dict[str, Any]] = []
    common = {
        "timestamp": timestamp,
        "session_id": session_id,
        "request_id": request_id,
        "turn_id": turn_id,
        "operations": operations,
    }

    if operations.get("memory_extraction_executed"):
        entries.append(
            {
                **common,
                "call_type": CALL_MEMORY_EXTRACTION,
                "endpoint": "internal/memory_extractor",
                "model": mem_usage.get("model") or "gpt-4o-mini",
                "input_tokens": int(mem_usage.get("input_tokens", 0)),
                "output_tokens": int(mem_usage.get("output_tokens", 0)),
                "total_tokens": int(mem_usage.get("total_tokens", 0)),
                "cost_usd": float(costs.get("memory_extraction_usd", 0.0)),
                "latency_ms": mem_usage.get("latency_ms"),
                "degraded": bool(operations.get("memory_extraction_degraded")),
            }
        )

    summary_usage = operations.get("summary_compression") or {}
    if not isinstance(summary_usage, dict):
        summary_usage = {}
    if operations.get("summary_compression_executed"):
        entries.append(
            {
                **common,
                "call_type": CALL_SUMMARY_COMPRESSION,
                "endpoint": "internal/summary_compression",
                "model": summary_usage.get("model") or "gpt-4o-mini",
                "input_tokens": int(summary_usage.get("input_tokens", 0)),
                "output_tokens": int(summary_usage.get("output_tokens", 0)),
                "total_tokens": int(summary_usage.get("total_tokens", 0)),
                "cost_usd": float(costs.get("summary_compression_usd", 0.0)),
                "latency_ms": summary_usage.get("latency_ms"),
                "degraded": bool(operations.get("summary_compression_degraded")),
            }
        )

    guardrails_on = bool(operations.get("guardrails_enabled"))
    moderation_ran = bool(operations.get("guardrails_moderation_executed"))
    guard_cost = float(costs.get("guardrails_usd", 0.0))
    if guardrails_on or guard_cost > 0:
        entries.append(
            {
                **common,
                "call_type": CALL_GUARDRAILS,
                "endpoint": "internal/guardrails",
                "cost_usd": guard_cost,
                "guardrails_enabled": guardrails_on,
                "guardrails_moderation_executed": moderation_ran,
                "status": "ejecutado" if moderation_ran else "activo (sin coste API)",
            }
        )

    cache_enabled = bool(operations.get("semantic_cache_enabled"))
    cache_lookup = bool(operations.get("cache_lookup_performed"))
    cache_embed = bool(operations.get("cache_embedding_computed"))
    embed_cost = float(costs.get("cache_embedding_usd", 0.0))
    if cache_enabled or cache_lookup or cache_embed or embed_cost > 0:
        entries.append(
            {
                **common,
                "call_type": CALL_CACHE_EMBEDDING,
                "endpoint": "internal/cache_embedding",
                "cost_usd": embed_cost,
                "semantic_cache_enabled": cache_enabled,
                "cache_lookup_performed": cache_lookup,
                "cache_embedding_computed": cache_embed,
                "cache_hit": bool(operations.get("cache_hit")),
                "cache_source": operations.get("cache_source"),
                "status": "embedding calculado" if cache_embed else "lookup sin embedding",
            }
        )

    return entries
