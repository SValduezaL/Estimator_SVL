"""Schemas de transporte para el endpoint de estimaciones."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.context.examples import ExampleFormat
from app.services.evaluation import EstimationStructureResult
from app.services.llm_service import GenerationOptions

PreprocessingMode = Literal["none", "inline_cleaning", "two_phase"]

class EstimationRequest(BaseModel):
    """Payload de entrada para solicitar una estimación."""

    transcription: str = Field(
        ...,
        min_length=50,
        description="Texto de la transcripción de reunión",
    )
    preprocessing: str = Field(
        default="none",
        description="Solo 'none' esta soportado actualmente.",
    )
    example_format: ExampleFormat = Field(
        default="markdown",
        description="Formato de serialización de ejemplos CAG en el system prompt.",
    )
    num_examples: int | None = Field(
        default=None,
        ge=0,
        description="Número de ejemplos few-shot; None = todos los disponibles.",
    )
    use_examples: bool = Field(default=True, description="Si False, omite el bloque de ejemplos del prompt.")
    model: str | None = Field(default=None, description="Override del modelo; debe estar permitido para el proveedor.")
    max_tokens: int | None = Field(
        default=4000,
        ge=100,
        le=16000,
        description="Override de max tokens de salida.",
    )
    thinking_budget: int | None = Field(
        default=None,
        ge=0,
        le=16000,
        description="Reservado para modelos con reasoning; ignorado por ahora.",
    )
    evaluate: bool = Field(
        default=False,
        description="Si True, ejecuta validación heurística del Markdown devuelto.",
    )
    skip_cache: bool = Field(
        default=False,
        description="Si True, no lee ni escribe la caché Redis para esta petición.",
    )

    @field_validator("preprocessing")
    @classmethod
    def preprocessing_only_none(cls, v: str) -> str:
        if v != "none":
            raise ValueError("Solo se admite preprocessing='none' por el momento.")
        return v

    def to_generation_options(self) -> GenerationOptions:
        return GenerationOptions(
            preprocessing=self.preprocessing,
            example_format=self.example_format,
            num_examples=self.num_examples,
            use_examples=self.use_examples,
            model=self.model,
            max_tokens=self.max_tokens,
            thinking_budget=self.thinking_budget,
            skip_cache=self.skip_cache,
        )


class StreamEstimationRequest(BaseModel):
    """Entrada para streaming (mismas palancas CAG que /estimate salvo `evaluate`)."""

    transcription: str = Field(
        ...,
        min_length=50,
        description="Transcripción de reunión.",
    )
    preprocessing: str = Field(
        default="none",
        description="Solo 'none' está soportado actualmente.",
    )
    example_format: ExampleFormat = Field(
        default="markdown",
        description="Formato de serialización de ejemplos CAG en el system prompt.",
    )
    num_examples: int | None = Field(
        default=None,
        ge=0,
        description="Número de ejemplos few-shot; None = todos los disponibles.",
    )
    use_examples: bool = Field(
        default=True,
        description="Si False, omite el bloque de ejemplos del prompt.",
    )
    model: str | None = Field(default=None, description="Override del modelo.")
    max_tokens: int | None = Field(
        default=4000,
        ge=100,
        le=16000,
        description="Override de max tokens.",
    )
    thinking_budget: int | None = Field(
        default=None,
        ge=0,
        le=16000,
        description="Reservado para modelos con reasoning; ignorado por ahora.",
    )
    skip_cache: bool = Field(
        default=False,
        description="Si True, no lee ni escribe la caché Redis para esta petición.",
    )

    @field_validator("preprocessing")
    @classmethod
    def preprocessing_only_none_stream(cls, v: str) -> str:
        if v != "none":
            raise ValueError("Solo se admite preprocessing='none' por el momento.")
        return v

    def to_generation_options(self) -> GenerationOptions:
        return GenerationOptions(
            preprocessing=self.preprocessing,
            example_format=self.example_format,
            num_examples=self.num_examples,
            use_examples=self.use_examples,
            model=self.model,
            max_tokens=self.max_tokens,
            thinking_budget=self.thinking_budget,
            skip_cache=self.skip_cache,
        )


class TokenUsage(BaseModel):
    """Desglose de consumo de tokens reportado por el proveedor LLM."""

    input_tokens: int = Field(..., ge=0, description="Tokens de entrada enviados al LLM")
    output_tokens: int = Field(..., ge=0, description="Tokens de salida generados por el LLM")
    total_tokens: int = Field(..., ge=0, description="Total de tokens consumidos")
    preprocessing_input_tokens: int = 0
    preprocessing_output_tokens: int = 0


class EstimationStructureValidation(BaseModel):
    """Resultado de validación de estructura (espejo de EstimationStructureResult)."""

    has_title: bool = False
    has_breakdown_table: bool = False
    has_totals_section: bool = False
    has_team_section: bool = False
    has_duration_section: bool = False
    declared_total_hours: int | None = None
    sum_row_hours: int | None = None
    hours_match: bool | None = False
    declared_total_cost: float | None = None
    sum_row_cost: float | None = None
    cost_match: bool | None = False
    finish_reason_ok: bool | None = True
    score: float = 0.0
    issues: list[str] = Field(default_factory=list)


def structure_result_to_schema(r: EstimationStructureResult) -> EstimationStructureValidation:
    return EstimationStructureValidation.model_validate(asdict(r))


class EstimationResponse(BaseModel):
    """Payload de salida normalizado por la capa de servicios."""

    estimation: str = Field(..., description="Estimación generada por el LLM")
    model: str = Field(..., description="Modelo LLM utilizado en la llamada")
    provider: str = Field(..., description="Proveedor LLM utilizado en la llamada")
    finish_reason: str = Field(..., description="Motivo de fin reportado por el proveedor")
    preprocessing: PreprocessingMode = "none"
    usage: TokenUsage
    validation: EstimationStructureValidation | None = Field(
        default=None,
        description="Métricas de estructura si se solicitó evaluate=true",
    )
    
    # --- Session 3 — wrapper metadata (additive, defaults preserve Session 2 tests) ---
    cache_hit: bool = Field(
        default=False,
        description="True cuando la respuesta viene de Redis"
    )
    cost_usd: float = Field(
        default=0.0,
        description="Coste estimado en función del número de tokens usados"
    )
