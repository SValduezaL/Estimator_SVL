"""Preparación de datos para gráficos Streamlit."""

from __future__ import annotations

from typing import Any


def bar_chart_by_call_type(cost_by_type: dict[str, float]) -> dict[str, float]:
    return {k: round(v, 6) for k, v in cost_by_type.items() if v > 0 or k}


def tokens_stacked_series(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Agrupa tokens in/out por tipo de llamada."""
    series: dict[str, dict[str, int]] = {}
    for row in rows:
        ct = str(row.get("call_type", "unknown"))
        if ct not in series:
            series[ct] = {"input": 0, "output": 0}
        series[ct]["input"] += int(row.get("input_tokens", 0))
        series[ct]["output"] += int(row.get("output_tokens", 0))
    return series


def latency_by_model(rows: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[int]] = {}
    for row in rows:
        model = str(row.get("model", "unknown"))
        buckets.setdefault(model, []).append(int(row.get("latency_ms", 0)))
    return {m: sum(v) / len(v) for m, v in buckets.items() if v}
