"""Schemas de transporte para el endpoint de estimaciones (Pydantic v2)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from pydantic import BaseModel, Field

ESTIMATION_PROMPT_VERSION: Final[str] = "estimation-v1"


class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


# Etiquetas UI (Streamlit u otros clientes) — misma fuente que los valores del enum.
PROJECT_TYPE_LABELS: dict[ProjectType, str] = {
    ProjectType.MOBILE_APP: "App móvil",
    ProjectType.WEB_SAAS: "Web / SaaS",
    ProjectType.INTERNAL_TOOL: "Herramienta interna",
    ProjectType.DATA_PIPELINE: "Pipeline de datos",
}

DETAIL_LEVEL_LABELS: dict[DetailLevel, str] = {
    DetailLevel.SUMMARY: "Resumen",
    DetailLevel.MEDIUM: "Medio",
    DetailLevel.DETAILED: "Detallado",
}

OUTPUT_FORMAT_LABELS: dict[OutputFormat, str] = {
    OutputFormat.PHASES_TABLE: "Tabla por fases",
    OutputFormat.LINE_ITEMS: "Partidas en tabla (horas / coste)",
    OutputFormat.NARRATIVE: "Narrativa",
}


@dataclass
class GenerationOptions:
    """Opciones por solicitud para caché y llamada al LLM (sin composición de prompts)."""

    model: str | None = None
    max_tokens: int | None = None
    thinking_budget: int | None = None
    skip_cache: bool = False
    project_type: str | None = None
    detail_level: str | None = None
    output_format: str | None = None


class EstimationRequest(BaseModel):
    """Entrada estructurada para solicitar una estimación (solo streaming)."""

    description: str = Field(
        min_length=20,
        max_length=2000,
        description="Descripción del alcance o contexto del proyecto",
    )
    project_type: ProjectType
    detail_level: DetailLevel
    output_format: OutputFormat

    def to_generation_options(self) -> GenerationOptions:
        return GenerationOptions(
            model=None,
            max_tokens=None,
            thinking_budget=None,
            skip_cache=False,
            project_type=self.project_type.value,
            detail_level=self.detail_level.value,
            output_format=self.output_format.value,
        )


class EstimationResponse(BaseModel):
    """Contrato de salida lógica (la entrega HTTP real es streaming SSE)."""

    text: str
    prompt_version: str
