"""Schemas de entrada para solicitar una estimación."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.schemas.estimation_common import DetailLevel, ProjectType


@dataclass
class GenerationOptions:
    """Opciones por solicitud para caché y llamada al LLM."""

    model: str | None = None
    max_tokens: int | None = None
    thinking_budget: int | None = None
    skip_cache: bool = False
    project_type: str | None = None
    detail_level: str | None = None


class EstimationRequest(BaseModel):
    """Entrada estructurada para solicitar una estimación."""

    description: str = Field(
        min_length=20,
        max_length=2000,
        description="Descripción del alcance o contexto del proyecto",
    )
    project_type: ProjectType
    detail_level: DetailLevel

    def to_generation_options(self) -> GenerationOptions:
        return GenerationOptions(
            model=None,
            max_tokens=None,
            thinking_budget=None,
            skip_cache=False,
            project_type=self.project_type.value,
            detail_level=self.detail_level.value,
        )
