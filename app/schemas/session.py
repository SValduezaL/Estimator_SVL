"""Schemas HTTP para sesiones conversacionales."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.memory.models import Message, ProjectMetadata


class SessionCreateResponse(BaseModel):
    """Respuesta de ``POST /api/v1/sessions``."""

    session_id: str


class SessionDetailResponse(BaseModel):
    """Estado de una sesión conversacional (``GET /api/v1/sessions/{session_id}``)."""

    session_id: str
    history: list[Message] = Field(default_factory=list)
    project_metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)
    created_at: datetime
    updated_at: datetime
