"""Carga y renderizado de prompts versionados (Jinja2).

Único punto de contacto entre Python y los artefactos .j2 bajo ``app/prompts/``.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.fixtures.estimation_examples import few_shot_json_block
from app.prompts.registry import DEFAULT_ESTIMATION_BUNDLE, PromptBundle
from app.schemas.estimation_common import ProjectType
from app.schemas.estimation_request import EstimationRequest

_PROMPTS_DIR = Path(__file__).resolve().parent
_PROMPT_RENDER_PART_SEPARATOR = "\n\n---PROMPT_RENDER_SEPARATOR---\n\n"
_log = structlog.get_logger(__name__)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _example_json_filter(project_type: str, scenario: int) -> str:
    return few_shot_json_block(ProjectType(project_type), scenario)


def build_estimation_jinja_environment() -> Environment:
    """Entorno Jinja2 para prompts de estimación (fail-fast con variables ausentes)."""
    env = Environment(
        loader=FileSystemLoader(_PROMPTS_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
        undefined=StrictUndefined,
    )
    env.globals["example_json"] = _example_json_filter
    return env


@lru_cache
def _cached_estimation_environment() -> Environment:
    return build_estimation_jinja_environment()


def clear_estimation_environment_cache() -> None:
    """Invalida el entorno Jinja cacheado (tests o recarga de filtros)."""
    _cached_estimation_environment.cache_clear()


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
    ctx: dict[str, str] = {
        "description": request.description,
        "project_type": request.project_type.value,
        "detail_level": request.detail_level.value,
        "_prompt_bundle_version": subdir,
        "_examples_template": f"estimation/{subdir}/examples.j2",
    }
    if subdir in ("v1", "v2"):
        ctx["output_format"] = "line_items"

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
