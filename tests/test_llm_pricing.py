"""Tests de resolución de precios por modelo."""

from app.foundation.llm.pricing import estimate_cost_usd, resolve_model_costs


def test_resolve_model_costs_versioned_openai_id() -> None:
    costs = resolve_model_costs("gpt-4o-mini-2024-07-18")
    assert costs == {"input": 0.15, "output": 0.60}


def test_resolve_model_costs_with_provider_prefix() -> None:
    costs = resolve_model_costs("openai/gpt-4o-mini-2024-07-18")
    assert costs == {"input": 0.15, "output": 0.60}


def test_estimate_cost_usd_matches_litellm_sample() -> None:
    # Tokens de la última llamada real (logs Docker, 2026-05-19).
    cost = estimate_cost_usd("gpt-4o-mini-2024-07-18", 1957, 289)
    assert cost == 0.000467
