"""HTTP para configuración de modelos en runtime."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.dependencies import get_runtime_config
from app.foundation.llm.pricing import provider_from_model
from app.foundation.llm.runtime_config import (
    MODEL_KEYS,
    RuntimeConfigUnavailable,
    RuntimeModelConfig,
)

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/config", tags=["config"])

EMBEDDING_MODEL_NOTE = "Solo lectura: cambiarlo invalidaría todos los vectores almacenados."


class ModelUpdateRequest(BaseModel):
    models: dict[str, str | None] = Field(min_length=1)


def _available_models(settings: Settings) -> list[str]:
    available: list[str] = []
    for models in settings.llm_models_by_provider.values():
        for model in models:
            prov = provider_from_model(model)
            if prov == "openai" and settings.openai_api_key:
                available.append(model)
            elif prov == "anthropic" and settings.anthropic_api_key:
                available.append(model)
    return sorted(set(available))


def _config_payload(runtime_config: RuntimeModelConfig, settings: Settings) -> dict:
    return {
        "models": runtime_config.snapshot(),
        "available_models": _available_models(settings),
        "embedding_model": settings.semantic_embedding_model,
        "embedding_model_note": EMBEDDING_MODEL_NOTE,
    }


@router.get("/models")
def get_models(
    runtime_config: RuntimeModelConfig | None = Depends(get_runtime_config),
    settings: Settings = Depends(get_settings),
) -> dict:
    if runtime_config is None:
        raise HTTPException(status_code=503, detail="Runtime config store unavailable")
    return _config_payload(runtime_config, settings)


@router.put("/models")
def update_models(
    request: ModelUpdateRequest,
    runtime_config: RuntimeModelConfig | None = Depends(get_runtime_config),
    settings: Settings = Depends(get_settings),
) -> dict:
    if runtime_config is None:
        raise HTTPException(status_code=503, detail="Runtime config store unavailable")

    available = _available_models(settings)
    all_models = set(available)
    for models in settings.llm_models_by_provider.values():
        all_models.update(models)

    for key, value in request.models.items():
        if key not in MODEL_KEYS:
            raise HTTPException(status_code=422, detail=f"Unknown model key: {key}")
        if value is None:
            continue
        if value not in all_models:
            raise HTTPException(status_code=422, detail=f"Model '{value}' is not in the catalog")
        if value not in available:
            prov = provider_from_model(value)
            raise HTTPException(
                status_code=400,
                detail=f"Model '{value}' requires API key for provider '{prov}'",
            )

    try:
        for key, value in request.models.items():
            old_effective = runtime_config.effective(key)
            runtime_config.set(key, value)
            log.info(
                "runtime_config_changed",
                key=key,
                old_effective=old_effective,
                new_value=value,
                reset=value is None,
            )
    except RuntimeConfigUnavailable as exc:
        log.error("runtime_config_write_failed", error=str(exc)[:200])
        raise HTTPException(status_code=503, detail="Runtime config store unavailable") from exc

    return _config_payload(runtime_config, settings)
