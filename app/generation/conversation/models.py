"""Modelos Pydantic de sesión, historial y metadata de proyecto."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.generation.conversation.constants import (
    MAX_ANCHORS,
    MAX_AGREED_SCOPE_LEN,
    MAX_LIST_ITEM_LEN,
    MAX_METADATA_LIST_ITEMS,
    MAX_METADATA_STRING_LEN,
    MAX_SUMMARY_CHARS,
)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _cap_string(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:max_len]


class ProjectMetadata(BaseModel):
    """Distilled facts about the project under estimation.

    Survives history truncation.
    """

    project_name: str | None = None
    assumed_team_size: int | None = None
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = None
    explicit_constraints: list[str] = Field(default_factory=list)
    rejected_options: list[str] = Field(default_factory=list)

    @field_validator(
        "mentioned_technologies",
        "explicit_constraints",
        "rejected_options",
        mode="before",
    )
    @classmethod
    def _coerce_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value]
        return []

    @model_validator(mode="before")
    @classmethod
    def _normalize_and_bound(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        def bound_list(items: object) -> list[str]:
            raw = [str(v) for v in items] if isinstance(items, list) else []
            cleaned = [
                s[:MAX_LIST_ITEM_LEN]
                for s in _dedupe_preserve_order(raw)
                if s.strip()
            ]
            return cleaned[:MAX_METADATA_LIST_ITEMS]

        team = data.get("assumed_team_size")
        if team is not None and (not isinstance(team, int) or team < 1 or team > 500):
            data["assumed_team_size"] = None

        data["project_name"] = _cap_string(
            data.get("project_name") if isinstance(data.get("project_name"), str) else None,
            MAX_METADATA_STRING_LEN,
        )
        data["agreed_scope"] = _cap_string(
            data.get("agreed_scope") if isinstance(data.get("agreed_scope"), str) else None,
            MAX_AGREED_SCOPE_LEN,
        )
        data["mentioned_technologies"] = bound_list(data.get("mentioned_technologies"))
        data["explicit_constraints"] = bound_list(data.get("explicit_constraints"))
        data["rejected_options"] = bound_list(data.get("rejected_options"))
        return data

    def is_empty(self) -> bool:
        return (
            self.project_name is None
            and self.assumed_team_size is None
            and not self.mentioned_technologies
            and self.agreed_scope is None
            and not self.explicit_constraints
            and not self.rejected_options
        )


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AnchorItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str = Field(min_length=1, max_length=120)
    fact: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    source_turn_index: int = Field(default=0, ge=0)
    last_confirmed_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["active", "deprecated"] = "active"


class RunningSummary(BaseModel):
    text: str = Field(default="", max_length=MAX_SUMMARY_CHARS)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    source_turn_upto: int = Field(default=0, ge=0)
    version: int = Field(default=1, ge=1)


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))

    history: list[Message] = Field(default_factory=list)
    anchors: list[AnchorItem] = Field(default_factory=list, max_length=MAX_ANCHORS)
    running_summary: RunningSummary | None = None

    project_metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    updated_at: datetime = Field(default_factory=datetime.utcnow)
