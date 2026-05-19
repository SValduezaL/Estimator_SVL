"""Carga y renderizado de prompts versionados (Jinja2).

Único punto de contacto entre Python y los artefactos .j2 bajo ``app/prompts/``.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.prompts.registry import DEFAULT_ESTIMATION_BUNDLE, PromptBundle
from app.schemas.estimation import EstimationRequest

_PROMPTS_DIR = Path(__file__).resolve().parent
_PROMPT_RENDER_PART_SEPARATOR = "\n\n---PROMPT_RENDER_SEPARATOR---\n\n"
_log = structlog.get_logger(__name__)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    *,
    bundle: PromptBundle | None = None,
    version: str | None = None,
) -> tuple[str, str]:
    """Renderiza `system.j2` y `user.j2` para el caso de uso *estimation*.

    Args:
        request: Petición validada (enums expuestos como ``.value`` en el contexto).
        bundle: Bundle registrado (``public_id`` + carpeta). Por defecto
            ``DEFAULT_ESTIMATION_BUNDLE`` (ver ``app/prompts/registry.py``).
        version: Solo para tests o migraciones: subcarpeta bajo ``estimation/``
            (p. ej. ``v1``). Si se informa, tiene prioridad sobre ``bundle``.

    Returns:
        Tupla ``(system_prompt, user_prompt)`` lista para el proveedor LLM.
    """
    if bundle is not None and version is not None:
        raise ValueError("Indica solo uno de: ``bundle`` o ``version``.")

    if version is not None:
        b = PromptBundle(
            use_case="estimation",
            public_id=f"estimation-{version}",
            template_subdir=version,
            created_at=DEFAULT_ESTIMATION_BUNDLE.created_at,
        )
    else:
        b = bundle or DEFAULT_ESTIMATION_BUNDLE

    if b.use_case != "estimation":
        raise ValueError(f"Solo se soporta use_case='estimation' en el loader actual ({b.use_case!r}).")

    subdir = b.template_subdir
    env = _cached_estimation_environment()
    ctx = {
        "description": request.description,
        "project_type": request.project_type.value,
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
        "_prompt_bundle_version": subdir,
        "_examples_template": f"estimation/{subdir}/examples.j2",
    }
    system_t = env.get_template(f"estimation/{subdir}/system.j2")
    user_t = env.get_template(f"estimation/{subdir}/user.j2")
    system_prompt = system_t.render(**ctx).strip()
    user_prompt = user_t.render(**ctx).strip()
    combined = f"system{_PROMPT_RENDER_PART_SEPARATOR}{system_prompt}{_PROMPT_RENDER_PART_SEPARATOR}user{_PROMPT_RENDER_PART_SEPARATOR}{user_prompt}"
    _log.info(
        "estimation_prompt_rendered",
        log_category="technical",
        prompt_version=b.public_id,
        content_sha256=_sha256_hex(combined),
    )
    return system_prompt, user_prompt
