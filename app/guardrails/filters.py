"""Filtros y respuestas degradadas (política FILTER)."""

from __future__ import annotations

import structlog

from app.schemas.estimation_common import LOW_CONFIDENCE_THRESHOLD, OUT_OF_SCOPE_PREFIX
from app.schemas.estimation_common import DetailLevel, ProjectType
from app.schemas.estimation_output import EstimationResult, Phase

log = structlog.get_logger(__name__)

_NOT_ESTIMATED_PHASE = Phase(
    name="Sin estimar",
    deliverable="No se puede dimensionar sin más información sobre alcance, integraciones y equipo.",
    stack=["N/A"],
    hours=1,
    cost_eur=0,
    risks_notes="Alcance insuficiente para estimar con confianza.",
)


def enforce_scope_response(result: EstimationResult) -> EstimationResult:
    """FILTER: reescribe resultado si baja confianza sin prefijo de fuera de alcance."""
    is_low = result.confidence_pct < LOW_CONFIDENCE_THRESHOLD
    already_marked = result.summary.startswith(OUT_OF_SCOPE_PREFIX)

    if not is_low or already_marked:
        return result

    log.info(
        "enforce_scope_response_filtering",
        log_category="guardrails",
        confidence_pct=result.confidence_pct,
        original_summary_chars=len(result.summary),
    )
    new_summary = (
        f"{OUT_OF_SCOPE_PREFIX} No hay información suficiente para estimar con confianza. "
        f"Razonamiento original: {result.summary[:400]}"
    )
    return EstimationResult(
        summary=new_summary[:1200],
        confidence_pct=result.confidence_pct,
        phases=[_NOT_ESTIMATED_PHASE],
        total_duration_weeks=1,
        total_cost_eur=0,
        reasoning=(
            "## Alcance\n"
            "La descripción no permite dimensionar fases ni costes de forma fiable."
        ),
    )


def build_safe_fallback(
    *,
    project_type: ProjectType | str,
    detail_level: DetailLevel | str,
    reason: str = "validation_failed",
) -> EstimationResult:
    """Respuesta segura estándar cuando la validación semántica falla irrecuperablemente."""
    _ = project_type, detail_level, reason
    summary = (
        f"{OUT_OF_SCOPE_PREFIX} No se pudo generar una estimación fiable. "
        "Amplíe la descripción del alcance, integraciones y restricciones."
    )
    return EstimationResult(
        summary=summary[:1200],
        confidence_pct=min(LOW_CONFIDENCE_THRESHOLD - 1, 30),
        phases=[_NOT_ESTIMATED_PHASE],
        total_duration_weeks=1,
        total_cost_eur=0,
        reasoning="## Alcance\nEstimación degradada por guardrails de salida.",
    )


def degrade_low_confidence(result: EstimationResult) -> EstimationResult:
    """Degradación elegante si confidence muy bajo pero estructura válida."""
    if result.confidence_pct >= LOW_CONFIDENCE_THRESHOLD:
        return result
    return enforce_scope_response(result)
