"""Servicio de integración LLM para estimaciones con arquitectura CAG.

La composición de prompts (system/user) vive en ``app/prompts/`` y se invoca vía
``render_estimation_prompt`` desde ``build_estimation_cache_inputs``.
"""

from app.config import Settings, get_settings
from app.memory.models import ProjectMetadata
from app.prompts.loader import render_estimation_prompt
from app.prompts.registry import DEFAULT_ESTIMATION_BUNDLE, PromptBundle
from app.schemas.estimation_request import EstimationRequest


def build_estimation_cache_inputs(
    *,
    settings: Settings,
    request: EstimationRequest,
    bundle: PromptBundle | None = None,
    project_metadata: ProjectMetadata | None = None,
) -> tuple[str, str, str, int, int | None, PromptBundle]:
    """Textos y parámetros que entran en la clave de caché y en la llamada al modelo."""
    b = bundle or DEFAULT_ESTIMATION_BUNDLE
    system_prompt, user_message = render_estimation_prompt(
        request,
        bundle=b,
        project_metadata=project_metadata,
    )
    opts = request.to_generation_options()
    model = opts.model if opts.model is not None else settings.llm_model
    max_tokens = opts.max_tokens if opts.max_tokens is not None else settings.max_tokens
    return system_prompt, user_message, model, max_tokens, opts.thinking_budget, b
