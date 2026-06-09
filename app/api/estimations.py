"""Router HTTP fino para estimaciones (POST /estimate)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import (
    get_async_openai_client,
    get_cache_orchestrator,
    get_estimation_service,
    get_openai_moderation_client,
)
from app.domain.estimation_service import EstimationService
from app.domain.exceptions import EstimationFailedError, PromptGuardrailError
from app.domain.schemas.estimation import EstimationRequest, EstimationResponse
from app.foundation.guardrails.exceptions import GuardrailBlocked
from app.foundation.llm.wrapper import LLMWrapper
from app.generation.cag import EstimationCacheOrchestrator
from app.generation.conversation.exceptions import SessionExpiredError, SessionNotFoundError

router = APIRouter(prefix="/api/v1", tags=["estimations"])


@router.post("/estimate", response_model=EstimationResponse)
async def create_estimation(
    request: EstimationRequest,
    service: EstimationService = Depends(get_estimation_service),
) -> EstimationResponse:
    try:
        return await service.estimate(request)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SessionExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except GuardrailBlocked as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except PromptGuardrailError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EstimationFailedError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc
