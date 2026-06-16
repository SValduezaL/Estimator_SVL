"""Architecture decision: CAG, RAG or hybrid? (Article 1 of the module)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

_CENTER_RECALL_TOKEN_BUDGET = 100_000
_USABLE_WINDOW_FRACTION = 0.7
_CACHE_FRIENDLY_REFRESH_DAYS = 7


@dataclass
class CAGViability:
    context_window_ok: bool
    cost_ok: bool
    latency_ok: bool
    lost_in_the_middle_ok: bool

    @property
    def viable(self) -> bool:
        return all(
            [
                self.context_window_ok,
                self.cost_ok,
                self.latency_ok,
                self.lost_in_the_middle_ok,
            ]
        )

    def failing_constraints(self) -> list[str]:
        return [
            name
            for name, ok in (
                ("context_window", self.context_window_ok),
                ("cost", self.cost_ok),
                ("latency", self.latency_ok),
                ("lost_in_the_middle", self.lost_in_the_middle_ok),
            )
            if not ok
        ]


@dataclass
class CorpusProfile:
    name: str
    estimated_tokens: int
    refresh_frequency_days: float
    traceability_required: bool
    access_control_required: bool


@dataclass
class ModelConfig:
    name: str
    context_window: int
    cost_per_1k_input: float
    prefix_caching: bool


def assess_cag_viability(corpus: CorpusProfile, model: ModelConfig) -> CAGViability:
    fits = corpus.estimated_tokens <= model.context_window * _USABLE_WINDOW_FRACTION
    return CAGViability(
        context_window_ok=fits,
        cost_ok=model.prefix_caching
        and corpus.refresh_frequency_days >= _CACHE_FRIENDLY_REFRESH_DAYS,
        latency_ok=corpus.estimated_tokens <= _CENTER_RECALL_TOKEN_BUDGET,
        lost_in_the_middle_ok=corpus.estimated_tokens <= _CENTER_RECALL_TOKEN_BUDGET,
    )


def recommend_architecture(
    corpus: CorpusProfile, model: ModelConfig
) -> Literal["CAG", "Hybrid", "RAG"]:
    fits_in_window = corpus.estimated_tokens <= model.context_window * _USABLE_WINDOW_FRACTION
    cache_friendly = corpus.refresh_frequency_days >= _CACHE_FRIENDLY_REFRESH_DAYS
    traceability_doable = not corpus.traceability_required
    access_control_doable = not corpus.access_control_required

    viable_for_cag = all(
        [fits_in_window, cache_friendly, traceability_doable, access_control_doable]
    )
    if viable_for_cag:
        return "CAG"
    if fits_in_window and cache_friendly:
        return "Hybrid"
    return "RAG"


PROYECTO_2 = CorpusProfile(
    name="Proyecto 2",
    estimated_tokens=250_000,
    refresh_frequency_days=7,
    traceability_required=True,
    access_control_required=True,
)

CURRENT_MODEL = ModelConfig(
    name="gpt-4o-mini",
    context_window=128_000,
    cost_per_1k_input=0.00015,
    prefix_caching=True,
)


def _main(argv: list[str]) -> int:
    corpus, model = PROYECTO_2, CURRENT_MODEL
    viability = assess_cag_viability(corpus, model)
    recommendation = recommend_architecture(corpus, model)

    print(
        f"Corpus '{corpus.name}': {corpus.estimated_tokens:,} tokens, "
        f"refresh cada {corpus.refresh_frequency_days:g} días, "
        f"trazabilidad={corpus.traceability_required}, "
        f"control_acceso={corpus.access_control_required}"
    )
    print(
        f"Modelo '{model.name}': ventana {model.context_window:,} tokens, "
        f"prefix_caching={model.prefix_caching}"
    )
    print()
    if viability.viable:
        print("Viabilidad CAG: viable (las 4 restricciones en verde)")
    else:
        print("Viabilidad CAG: NO viable")
        print(f"  Restricciones en rojo: {', '.join(viability.failing_constraints())}")
    print(f"Recomendación arquitectónica: {recommendation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
