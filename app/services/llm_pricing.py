"""Precios por modelo (USD / 1M tokens) y utilidades para estimar coste de llamadas LLM.

Actualiza ``MODEL_COSTS`` cuando cambien las tarifas públicas de los proveedores.
Los valores son orientativos para métricas internas, no facturación legal.
"""

from __future__ import annotations

# Coste por 1M tokens (USD): clave = id de modelo sin prefijo ``proveedor/``.
MODEL_COSTS: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-3-5-haiku-latest": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
}


def normalise_model_name(model: str) -> str:
    """Quita prefijos tipo ``anthropic/`` que LiteLLM puede emitir en ``response.model``."""
    return model.split("/", 1)[1] if "/" in model else model


def provider_from_model(model: str) -> str:
    """Heurística de proveedor a partir del id de modelo (post-normalización)."""
    name = normalise_model_name(model).lower()
    if name.startswith("claude"):
        return "anthropic"
    if name.startswith("gpt") or name.startswith("o1") or name.startswith("o3"):
        return "openai"
    return "unknown"


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estima coste USD a partir de tokens y ``MODEL_COSTS``."""
    base = normalise_model_name(model)
    costs = MODEL_COSTS.get(base) or MODEL_COSTS.get(model) or {"input": 0.0, "output": 0.0}
    return round((tokens_in * costs["input"] + tokens_out * costs["output"]) / 1_000_000, 6)
