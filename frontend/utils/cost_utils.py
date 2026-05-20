"""Agregaciones de costes y tokens."""

from __future__ import annotations

from typing import Any

from frontend.styles.constants import (
    CALL_CACHE_EMBEDDING,
    CALL_ESTIMATION,
    CALL_GUARDRAILS,
    CALL_MEMORY_EXTRACTION,
)


def aggregate_call_log(
    call_log: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    call_type: str | None = None,
) -> dict[str, Any]:
    rows = call_log
    if session_id and session_id != "all":
        rows = [r for r in rows if r.get("session_id") == session_id]
    if call_type and call_type != "all":
        rows = [r for r in rows if r.get("call_type") == call_type]

    total_cost = sum(float(r.get("cost_usd", 0.0)) for r in rows)
    total_in = sum(int(r.get("input_tokens", 0)) for r in rows)
    total_out = sum(int(r.get("output_tokens", 0)) for r in rows)
    hits = sum(1 for r in rows if r.get("cache_hit"))
    misses = sum(1 for r in rows if r.get("cache_hit") is False)
    latencies = [int(r.get("latency_ms", 0)) for r in rows if r.get("latency_ms")]

    by_type: dict[str, float] = {
        CALL_ESTIMATION: 0.0,
        CALL_MEMORY_EXTRACTION: 0.0,
        CALL_GUARDRAILS: 0.0,
        CALL_CACHE_EMBEDDING: 0.0,
    }
    for row in rows:
        ct = str(row.get("call_type", CALL_ESTIMATION))
        breakdown = row.get("cost_breakdown")
        if isinstance(breakdown, dict):
            for k, v in breakdown.items():
                by_type[k] = by_type.get(k, 0.0) + float(v)
        else:
            by_type[ct] = by_type.get(ct, 0.0) + float(row.get("cost_usd", 0.0))

    return {
        "count": len(rows),
        "total_cost_usd": total_cost,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "cache_hits": hits,
        "cache_misses": misses,
        "cache_hit_ratio": hits / (hits + misses) if (hits + misses) else 0.0,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        "cost_by_type": by_type,
        "rows": rows,
    }


def cost_timeline(call_log: list[dict[str, Any]]) -> dict[str, float]:
    """Serie temporal acumulada de coste por timestamp."""
    ordered = sorted(call_log, key=lambda r: r.get("timestamp", ""))
    out: dict[str, float] = {}
    acc = 0.0
    for row in ordered:
        ts = str(row.get("timestamp", ""))[:16]
        if not ts:
            continue
        acc += float(row.get("cost_usd", 0.0))
        out[ts] = round(acc, 6)
    return out
