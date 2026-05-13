"""Carga y renderizado de prompts versionados (Jinja2).

Único punto de contacto entre Python y los artefactos `.j2` bajo `app/prompts/`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.schemas.estimation import EstimationRequest

_PROMPTS_DIR = Path(__file__).resolve().parent

DEFAULT_ESTIMATION_TEMPLATE_VERSION: Final[str] = "v1"


def build_estimation_jinja_environment() -> Environment:
    """Entorno Jinja2 para prompts de estimación (fail-fast con variables ausentes)."""
    return Environment(
        loader=FileSystemLoader(_PROMPTS_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
        undefined=StrictUndefined,
    )


@lru_cache
def _cached_estimation_environment() -> Environment:
    return build_estimation_jinja_environment()


def render_estimation_prompt(
    request: EstimationRequest,
    version: str = "v1",
) -> tuple[str, str]:
    """Renderiza `system.j2` y `user.j2` para el caso de uso *estimation*.

    Args:
        request: Petición validada (enums expuestos como `.value` en el contexto).
        version: Subcarpeta bajo `estimation/` (p. ej. ``v1`` para rollback / evals).

    Returns:
        Tupla ``(system_prompt, user_prompt)`` lista para el proveedor LLM.
    """
    env = _cached_estimation_environment()
    ctx = {
        "description": request.description,
        "project_type": request.project_type.value,
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
        "_prompt_bundle_version": version,
        "_examples_template": f"estimation/{version}/examples.j2",
    }
    system_t = env.get_template(f"estimation/{version}/system.j2")
    user_t = env.get_template(f"estimation/{version}/user.j2")
    return system_t.render(**ctx).strip(), user_t.render(**ctx).strip()
