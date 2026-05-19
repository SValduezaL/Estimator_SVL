"""Capa HTTP: respuesta del endpoint de estimaciones."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.estimation_common import SCHEMA_VERSION
from app.schemas.estimation_output import EstimationResult

# Re-exports para compatibilidad de imports existentes
from app.schemas.estimation_common import (  # noqa: F401
    DETAIL_LEVEL_LABELS,
    PROJECT_TYPE_LABELS,
    DetailLevel,
    ProjectType,
)
from app.schemas.estimation_request import EstimationRequest, GenerationOptions  # noqa: F401


class TokenUsageResponse(BaseModel):
    """Consumo de tokens de una estimación."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class EstimationResponse(BaseModel):
    """Respuesta JSON de ``POST /api/v1/estimate``."""

    result: EstimationResult
    schema_version: Literal["estimation.v1"] = SCHEMA_VERSION
    prompt_version: str
    prompt_version_created_at: str
    model: str
    provider: str
    usage: TokenUsageResponse
    usage_available: bool
    cache_hit: bool
    finish_reason: str
    cost_usd: float
    response_seconds: float
