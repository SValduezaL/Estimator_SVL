"""Métricas desglosadas por tipo de operación en una estimación."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OperationCosts(BaseModel):
    """Costes USD por categoría de llamada."""

    estimation_usd: float = 0.0
    memory_extraction_usd: float = 0.0
    summary_compression_usd: float = 0.0
    guardrails_usd: float = 0.0
    cache_embedding_usd: float = 0.0
    total_usd: float = 0.0


class OperationUsage(BaseModel):
    """Tokens de una operación puntual."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str | None = None
    latency_ms: int | None = None


class EstimationOperationsMetrics(BaseModel):
    """Telemetría expuesta al cliente (p. ej. UI Streamlit)."""

    costs: OperationCosts = Field(default_factory=OperationCosts)
    memory_extraction: OperationUsage = Field(default_factory=OperationUsage)
    summary_compression: OperationUsage = Field(default_factory=OperationUsage)
    memory_extraction_executed: bool = False
    memory_extraction_degraded: bool = False
    summary_compression_executed: bool = False
    summary_compression_degraded: bool = False
    tier_decision: dict[str, object] | None = None
    guardrails_enabled: bool = False
    guardrails_moderation_executed: bool = False
    semantic_cache_enabled: bool = False
    cache_lookup_performed: bool = False
    cache_embedding_computed: bool = False
    cache_hit: bool = False
    cache_source: str | None = None
