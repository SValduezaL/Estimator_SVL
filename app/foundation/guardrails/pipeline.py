"""Fachada del pipeline de guardrails."""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.foundation.guardrails.input import run_input_guardrails
from app.foundation.guardrails.output import run_output_guardrails
from app.foundation.guardrails.prompts import validate_rendered_prompts
from app.foundation.guardrails.types import InputGuardrailResult
from app.domain.schemas.estimation_common import DetailLevel, ProjectType
from app.domain.schemas.estimation_output import EstimationResult

__all__ = [
    "run_input_guardrails",
    "run_output_guardrails",
    "validate_rendered_prompts",
    "InputGuardrailResult",
]


def guardrails_enabled(settings: Settings) -> bool:
    return settings.guardrails_enabled


def create_openai_client(settings: Settings) -> Any | None:
    """Cliente OpenAI solo para moderación (si hay API key)."""
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=settings.openai_api_key)
    except Exception:
        return None
