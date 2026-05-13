"""Registro central de bundles de prompts versionados (metadatos + carpeta de plantillas).

Cada ``PromptBundle`` enlaza un ``public_id`` estable (contrato API / métricas) con la
subcarpeta bajo ``app/prompts/<use_case>/`` y una **fecha de referencia** de creación
del bundle (sin codificarla en el nombre de la versión).

Para añadir otro caso de uso en el futuro (p. ej. resúmenes), define nuevos bundles con
otro ``use_case`` y amplía el loader correspondiente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final


@dataclass(frozen=True, slots=True)
class PromptBundle:
    """Identidad de un conjunto de plantillas Jinja2 versionadas."""

    use_case: str
    public_id: str
    template_subdir: str
    created_at: date


# --- Estimation (CAG) ---------------------------------------------------------

ESTIMATION_BUNDLE_V1: Final[PromptBundle] = PromptBundle(
    use_case="estimation",
    public_id="estimation-v1",
    template_subdir="v1",
    created_at=date(2026, 5, 12),
)

ESTIMATION_BUNDLE_V2: Final[PromptBundle] = PromptBundle(
    use_case="estimation",
    public_id="estimation-v2",
    template_subdir="v2",
    created_at=date(2026, 5, 13),
)

DEFAULT_ESTIMATION_BUNDLE: Final[PromptBundle] = ESTIMATION_BUNDLE_V2

ESTIMATION_BUNDLES_BY_PUBLIC_ID: Final[dict[str, PromptBundle]] = {
    ESTIMATION_BUNDLE_V1.public_id: ESTIMATION_BUNDLE_V1,
    ESTIMATION_BUNDLE_V2.public_id: ESTIMATION_BUNDLE_V2,
}

# Contrato estable para clientes / tests (equivale a ``DEFAULT_ESTIMATION_BUNDLE.public_id``)
ESTIMATION_PROMPT_VERSION: Final[str] = DEFAULT_ESTIMATION_BUNDLE.public_id


def get_estimation_bundle(public_id: str) -> PromptBundle:
    """Resuelve un bundle de estimación por ``public_id`` o falla con ``KeyError``."""
    return ESTIMATION_BUNDLES_BY_PUBLIC_ID[public_id]


# --- Extensión a otros casos de uso -----------------------------------------
# Patrón recomendado: nuevos ``PromptBundle`` con otro ``use_case`` (p. ej. ``summarization``)
# y un loader dedicado o una rama en un loader genérico que resuelva
# ``{use_case}/{template_subdir}/*.j2``. Mantén un dict ``*_BUNDLES_BY_PUBLIC_ID`` análogo
# al de estimación para resolución estable por contrato API.
