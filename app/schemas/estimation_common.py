"""Enums, constantes y etiquetas compartidas para estimaciones."""

from __future__ import annotations

from enum import Enum

SCHEMA_VERSION = "estimation.v1"

LOW_CONFIDENCE_THRESHOLD = 40
OUT_OF_SCOPE_PREFIX = "[FUERA_DE_ALCANCE]"

REASONING_BOUNDS: dict[str, tuple[int, int]] = {
    # Límites de ``reasoning`` (CoT de decisiones). El máximo es orientativo (truncado si excede).
    "summary": (100, 700),
    "medium": (200, 1400),
    "detailed": (400, 4000),
}


class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


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
