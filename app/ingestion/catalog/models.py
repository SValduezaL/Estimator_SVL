"""Pydantic v2 models for the data-source catalog."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CatalogDecision(str, Enum):
    INCLUDE = "include"
    REVIEW = "review"
    EXCLUDE = "exclude"


class QualityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completeness: int = Field(ge=1, le=5)
    consistency: int = Field(ge=1, le=5)
    actuality: int = Field(ge=1, le=5)
    reliability: int = Field(ge=1, le=5)


class Sensitivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_pii: bool
    pii_flags: list[str] = Field(default_factory=list)
    access_level: Literal["public", "internal", "confidential"] = "internal"


class CatalogSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    location: str
    owners: list[str] = Field(default_factory=list)
    format: Literal["json", "txt", "xlsx", "docx", "pdf", "csv"]
    volume_estimate: str = ""
    refresh_declared: str = ""
    refresh_observed: str = ""
    quality: QualityScore
    sensitivity: Sensitivity
    lineage: list[str] = Field(default_factory=list)
    decision: CatalogDecision
    decision_reason: str = ""
    last_audited: datetime | None = None

    @field_validator("name")
    @classmethod
    def _name_is_snake_case(cls, value: str) -> str:
        if not value or not all(c.islower() or c.isdigit() or c == "_" for c in value):
            raise ValueError(
                "CatalogSource.name must be lowercase snake_case "
                "(used as identifier in the ingestion endpoint)"
            )
        return value

    @model_validator(mode="after")
    def _decision_requires_reason_when_not_include(self) -> CatalogSource:
        if self.decision is not CatalogDecision.INCLUDE and not self.decision_reason:
            raise ValueError(f"decision={self.decision.value} requires a non-empty decision_reason")
        return self


class DataCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    description: str = ""
    sources: list[CatalogSource]

    @field_validator("sources")
    @classmethod
    def _names_are_unique(cls, sources: list[CatalogSource]) -> list[CatalogSource]:
        seen: set[str] = set()
        for src in sources:
            if src.name in seen:
                raise ValueError(f"Duplicate source name in catalog: {src.name}")
            seen.add(src.name)
        return sources

    def included_sources(self) -> list[CatalogSource]:
        return [s for s in self.sources if s.decision is CatalogDecision.INCLUDE]

    def find(self, name: str) -> CatalogSource | None:
        for src in self.sources:
            if src.name == name:
                return src
        return None
