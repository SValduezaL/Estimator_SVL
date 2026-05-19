"""Constantes y helpers de configuración de guardrails."""

from __future__ import annotations

GUARDRAILS_VERSION = "guardrails.v1"

# EUR/h implícito para coherencia de costes (validación semántica output)
DEFAULT_MIN_EUR_PER_HOUR = 20
DEFAULT_MAX_EUR_PER_HOUR = 250

# Horas por semana de referencia para coherencia temporal
DEFAULT_HOURS_PER_WEEK = 40
