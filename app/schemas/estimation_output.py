"""Modelo de dominio devuelto por el LLM (estructurado y validado)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.estimation_common import LOW_CONFIDENCE_THRESHOLD, OUT_OF_SCOPE_PREFIX

StackItem = Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]


class Phase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    deliverable: str = Field(min_length=5, max_length=400)
    stack: list[StackItem] = Field(
        min_length=1,
        max_length=12,
        description="Tecnologías, frameworks y servicios usados en el desarrollo de la fase.",
    )
    hours: int = Field(ge=1, le=2000)
    cost_eur: int = Field(ge=0, le=500_000)
    risks_notes: str | None = Field(default=None, max_length=500)
    confidence_pct: int | None = Field(default=None, ge=0, le=100)


class EstimationResult(BaseModel):
    """Structured estimation. Field order is deliberate: phases before totals."""

    summary: str = Field(min_length=10, max_length=1200)
    confidence_pct: int = Field(ge=0, le=100)
    phases: list[Phase] = Field(min_length=1, max_length=8)
    total_duration_weeks: int = Field(ge=1, le=104)
    total_cost_eur: int = Field(ge=0, le=2_000_000)
    reasoning: str = Field(
        min_length=1,
        description=(
            "Markdown en español: cadena de razonamiento que explica cómo se llegó "
            "a summary y phases (por qué N fases, por qué el stack de cada fase, "
            "por qué las horas de cada fase). No repite listas de tecnologías "
            "(están en phases[].stack), ni totales de coste, duración ni tarifas."
        ),
    )

    @model_validator(mode="after")
    def phases_sum_matches_total(self) -> EstimationResult:
        phase_sum = sum(p.cost_eur for p in self.phases)
        if phase_sum != self.total_cost_eur:
            raise ValueError(
                f"phases sum ({phase_sum} EUR) does not match total_cost_eur "
                f"({self.total_cost_eur} EUR); adjust either the phases or the total"
            )
        return self

    @model_validator(mode="after")
    def low_confidence_requires_out_of_scope_prefix(self) -> EstimationResult:
        if self.confidence_pct < LOW_CONFIDENCE_THRESHOLD and not self.summary.startswith(
            OUT_OF_SCOPE_PREFIX
        ):
            raise ValueError(
                f"confidence_pct < {LOW_CONFIDENCE_THRESHOLD} requires summary to "
                f"start with {OUT_OF_SCOPE_PREFIX!r}; refuse the estimation if the "
                f"description is too vague to size"
            )
        return self
