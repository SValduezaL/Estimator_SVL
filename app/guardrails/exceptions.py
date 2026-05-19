"""Excepciones del sistema de guardrails."""

from __future__ import annotations

from typing import Any, Literal

InputViolationReason = Literal["moderation", "prompt_injection", "pii"]


class InputGuardrailViolation(Exception):
    """Entrada rechazada por guardrails (HTTP 400)."""

    def __init__(self, message: str, *, reason: InputViolationReason) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class GuardrailBlocked(Exception):
    """Guardrail bloqueó el pipeline (input u output no recuperable)."""

    def __init__(
        self,
        message: str,
        *,
        phase: Literal["input", "output"],
        guardrail_name: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.phase = phase
        self.guardrail_name = guardrail_name


class OutputGuardrailRetryable(Exception):
    """Salida inválida pero recuperable con reintento LLM."""

    def __init__(
        self,
        message: str,
        *,
        guardrail_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.guardrail_name = guardrail_name
        self.metadata = metadata or {}


class ModerationUnavailable(Exception):
    """Moderación no disponible cuando fail-closed está activo."""

    pass
