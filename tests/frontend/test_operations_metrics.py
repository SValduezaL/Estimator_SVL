"""Tests de parsing de operations en métricas frontend."""

from __future__ import annotations

import pytest

from frontend.api.metrics import (
    build_operation_call_log_entries,
    parse_estimation_metrics,
    total_cost_from_response,
)
from frontend.styles.constants import (
    CALL_CACHE_EMBEDDING,
    CALL_ESTIMATION,
    CALL_MEMORY_EXTRACTION,
    CALL_SUMMARY_COMPRESSION,
)


def test_total_cost_from_operations() -> None:
    response = {
        "cost_usd": 0.05,
        "operations": {
            "costs": {
                "estimation_usd": 0.05,
                "memory_extraction_usd": 0.002,
                "summary_compression_usd": 0.001,
                "guardrails_usd": 0.0,
                "cache_embedding_usd": 0.0001,
            },
            "memory_extraction_executed": True,
            "guardrails_enabled": True,
            "semantic_cache_enabled": True,
            "cache_embedding_computed": True,
        },
    }
    assert total_cost_from_response(response) == pytest.approx(0.0531, rel=1e-4)


def test_build_operation_call_log_entries() -> None:
    response = {
        "operations": {
            "costs": {
                "estimation_usd": 0.1,
                "memory_extraction_usd": 0.01,
                "summary_compression_usd": 0.005,
                "guardrails_usd": 0.0,
                "cache_embedding_usd": 0.0002,
            },
            "memory_extraction_executed": True,
            "summary_compression_executed": True,
            "memory_extraction": {
                "model": "gpt-4o-mini",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "latency_ms": 200,
            },
            "summary_compression": {
                "model": "gpt-4o-mini",
                "input_tokens": 60,
                "output_tokens": 20,
                "total_tokens": 80,
                "latency_ms": 120,
            },
            "guardrails_enabled": True,
            "guardrails_moderation_executed": False,
            "semantic_cache_enabled": True,
            "cache_lookup_performed": True,
            "cache_embedding_computed": True,
            "cache_hit": False,
        }
    }
    entries = build_operation_call_log_entries(
        response,
        timestamp="2026-05-20T12:00:00",
        session_id="sess-1",
        request_id="req-1",
    )
    types = {e["call_type"] for e in entries}
    assert CALL_MEMORY_EXTRACTION in types
    assert CALL_SUMMARY_COMPRESSION in types
    assert CALL_CACHE_EMBEDDING in types
    assert entries[0]["cost_usd"] == 0.01


def test_parse_estimation_metrics_reads_operations() -> None:
    response = {
        "model": "gpt-test",
        "provider": "openai",
        "cost_usd": 0.08,
        "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        "operations": {
            "costs": {
                "estimation_usd": 0.08,
                "memory_extraction_usd": 0.003,
                "summary_compression_usd": 0.001,
                "guardrails_usd": 0.0,
                "cache_embedding_usd": 0.0,
            }
        },
    }
    row = parse_estimation_metrics(response)
    assert row["cost_breakdown"][CALL_ESTIMATION] == 0.08
    assert row["cost_breakdown"][CALL_MEMORY_EXTRACTION] == 0.003
    assert row["cost_breakdown"][CALL_SUMMARY_COMPRESSION] == 0.001
