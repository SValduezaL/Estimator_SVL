"""The canonical ``Document`` model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_version: str
    ingested_at: datetime
    lineage: list[str] = Field(default_factory=list)
    sensitivity_pii_flags: list[str] = Field(default_factory=list)
    sensitivity_access_level: str = "internal"
    location: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    metadata: DocumentMetadata
