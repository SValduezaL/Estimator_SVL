"""Schemas de transporte para el endpoint de estimaciones (Pydantic v2)."""

from __future__ import annotations

from enum import Enum
from typing import Final

from pydantic import BaseModel, Field

from app.context.examples import ExampleFormat
from app.services.llm_service import GenerationOptions

ESTIMATION_PROMPT_VERSION: Final[str] = "2026-05-13-v1"


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


def _example_format_for_output(fmt: OutputFormat) -> ExampleFormat:
    if fmt == OutputFormat.NARRATIVE:
        return "narrative"
    return "markdown"


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
            preprocessing="none",
            example_format=_example_format_for_output(self.output_format),
            num_examples=None,
            use_examples=True,
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
