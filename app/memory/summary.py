"""Resumen acumulativo por sesión con llamada LLM independiente."""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.memory.constants import MAX_SUMMARY_CHARS
from app.memory.models import Message, RunningSummary, Session
from app.services.llm_pricing import estimate_cost_usd

log = structlog.get_logger(__name__)


async def update_running_summary_llm(
    session: Session,
    *,
    removed_messages: list[Message],
    client: Any,
    model: str,
    max_chars: int = MAX_SUMMARY_CHARS,
) -> tuple[Session, dict[str, Any]]:
    """Actualiza resumen continuo; en fallo conserva el resumen anterior."""
    previous = session.running_summary.text if session.running_summary else ""
    removed_text = "\n".join(f"{m.role}: {m.content}" for m in removed_messages)
    if not removed_text.strip():
        return session, {
            "executed": False,
            "degraded": False,
            "cost_usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "model": model,
            "latency_ms": 0,
        }

    prompt = (
        "Resume conversational context preserving commitments and constraints.\n"
        "Return JSON with key 'summary'.\n\n"
        f"Previous summary:\n{previous}\n\n"
        f"New removed messages:\n{removed_text}"
    )
    t0 = time.perf_counter()
    try:
        if client is None:
            raise ValueError("Summary client not configured")
        response = await client.responses.create(
            model=model,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "running_summary",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"summary": {"type": "string"}},
                        "required": ["summary"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        parsed = json.loads(response.output_text or "{}")
        summary_text = str(parsed.get("summary", "")).strip()[:max_chars]
        if summary_text:
            prev_version = session.running_summary.version if session.running_summary else 0
            session.running_summary = RunningSummary(
                text=summary_text,
                source_turn_upto=len(session.history),
                version=prev_version + 1,
            )
        usage = getattr(response, "usage", None)
        in_t = int(getattr(usage, "input_tokens", 0) or 0)
        out_t = int(getattr(usage, "output_tokens", 0) or 0)
        total_t = int(getattr(usage, "total_tokens", in_t + out_t) or (in_t + out_t))
        cost = estimate_cost_usd(model, in_t, out_t)
        return session, {
            "executed": True,
            "degraded": False,
            "cost_usd": float(cost),
            "input_tokens": in_t,
            "output_tokens": out_t,
            "total_tokens": total_t,
            "model": model,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("summary_compression_degraded", error=str(exc))
        # fail-safe: preservar summary anterior
        if previous and session.running_summary is None:
            session.running_summary = RunningSummary(text=previous)
        return session, {
            "executed": True,
            "degraded": True,
            "error": str(exc),
            "cost_usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "model": model,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }
