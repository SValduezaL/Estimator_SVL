"""Schemas de transporte para el endpoint de estimaciones."""

from pydantic import BaseModel, Field


class EstimationRequest(BaseModel):
    """Payload de entrada para solicitar una estimacion."""

    transcription: str = Field(
        ...,
        min_length=20,
        description="Texto de la transcripcion de reunion",
    )


class TokenUsage(BaseModel):
    """Desglose de consumo de tokens reportado por el proveedor LLM."""

    input_tokens: int = Field(..., ge=0, description="Tokens de entrada enviados al LLM")
    output_tokens: int = Field(..., ge=0, description="Tokens de salida generados por el LLM")
    total_tokens: int = Field(..., ge=0, description="Total de tokens consumidos")


class EstimationResponse(BaseModel):
    """Payload de salida normalizado por la capa de servicios."""

    estimation: str = Field(..., description="Estimacion generada por el LLM")
    model: str = Field(..., description="Modelo LLM utilizado en la llamada")
    usage: TokenUsage