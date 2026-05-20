"""Formateo de números, fechas y texto."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def format_usd(value: float, precision: int = 6) -> str:
    return f"${value:.{precision}f}"


def format_tokens(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def format_latency_ms(ms: int | float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.2f} s"
    return f"{int(ms)} ms"


def format_timestamp(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso[:19] if len(iso) > 19 else iso


def truncate(text: str, max_len: int = 120) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def safe_str(value: Any) -> str:
    if value is None:
        return "—"
    return str(value)
