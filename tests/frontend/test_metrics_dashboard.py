"""Tests de preparación de datos para dashboard."""

from __future__ import annotations

from frontend.api.metrics import parse_estimation_metrics
from frontend.utils.charts import bar_chart_by_call_type, latency_by_model


def test_parse_estimation_metrics_defaults() -> None:
    row = parse_estimation_metrics(
        {
            "model": "gpt-4o-mini",
            "provider": "openai",
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            "cost_usd": 0.012,
            "cache_hit": False,
            "response_seconds": 1.5,
        },
        session_id="sess-1",
    )
    assert row["input_tokens"] == 100
    assert row["cost_breakdown"]["estimation"] == 0.012
    assert row["session_id"] == "sess-1"


def test_parse_extended_metrics_block() -> None:
    row = parse_estimation_metrics(
        {
            "cost_usd": 0.02,
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "metrics": {
                "costs": {
                    "estimation_usd": 0.015,
                    "memory_extraction_usd": 0.004,
                    "guardrails_usd": 0.001,
                }
            },
        }
    )
    assert row["cost_breakdown"]["memory_extraction"] == 0.004


def test_charts_helpers() -> None:
    assert bar_chart_by_call_type({"estimation": 0.01, "guardrails": 0.0})
    lat = latency_by_model([{"model": "gpt-4o-mini", "latency_ms": 100}, {"model": "gpt-4o-mini", "latency_ms": 200}])
    assert lat["gpt-4o-mini"] == 150.0
