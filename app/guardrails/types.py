"""Tipos compartidos del pipeline de guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class FailurePolicy(str, Enum):
    EXCEPTION = "exception"
    FILTER = "filter"
    RETRY = "retry"
    LOG_ONLY = "log_only"

InputViolationReason = Literal["moderation", "prompt_injection", "pii"]


@dataclass(frozen=True)
class GuardrailCheckResult:
    """Resultado de una capa individual de guardrail."""

    name: str
    passed: bool
    policy: FailurePolicy
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    filtered_text: str | None = None


@dataclass
class InputGuardrailResult:
    """Salida del pipeline de entrada (texto posiblemente redactado)."""

    text: str
    checks: list[GuardrailCheckResult] = field(default_factory=list)


@dataclass
class ModerationScores:
    """Scores de categorías de moderación OpenAI."""

    flagged: bool
    categories: list[str]
    category_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class OutputGuardrailContext:
    """Contexto para validación de salida."""

    detail_level: str
    project_type: str
