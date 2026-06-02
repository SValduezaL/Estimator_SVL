"""Router HTTP para sesiones conversacionales."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.attachments import (
    AttachmentExtractionError,
    UnsupportedAttachmentError,
    enrich_transcript,
    extract_text,
)
from app.config import Settings, get_settings
from app.dependencies import (
    get_async_openai_client,
    get_cache_orchestrator,
    get_llm_wrapper,
    get_openai_moderation_client,
)
from app.memory.exceptions import SessionExpiredError, SessionNotFoundError
from app.memory.store import create_session, get_session
from app.routers.estimations import run_estimation_pipeline
from app.schemas.estimation import EstimationRequest, EstimationResponse
from app.schemas.estimation_common import DetailLevel, ProjectType
from app.schemas.session import SessionCreateResponse, SessionDetailResponse
from app.services.llm_wrapper import LLMWrapper
from app.cache import EstimationCacheOrchestrator

router = APIRouter(prefix="/api/v1", tags=["sessions"])
log = structlog.get_logger(__name__)


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_conversation_session() -> SessionCreateResponse:
    """Crea una sesión vacía (reset explícito: nueva sesión sin memoria previa)."""
    session = create_session()
    log.info(
        "session_endpoint_created",
        log_category="business",
        session_id=session.session_id,
    )
    return SessionCreateResponse(session_id=session.session_id)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def read_conversation_session(session_id: str) -> SessionDetailResponse:
    """Devuelve historial y metadata de proyecto de la sesión."""
    try:
        session = get_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SessionExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    return SessionDetailResponse(
        session_id=session.session_id,
        history=session.history,
        anchors=session.anchors,
        running_summary=session.running_summary,
        project_metadata=session.project_metadata,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post("/sessions/{session_id}/estimate", response_model=EstimationResponse)
async def estimate_in_session(
    session_id: str,
    description: str = Form(...),
    project_type: ProjectType = Form(...),
    detail_level: DetailLevel = Form(...),
    files: list[UploadFile] | None = File(default=None),
    settings: Settings = Depends(get_settings),
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
    orchestrator: EstimationCacheOrchestrator | None = Depends(get_cache_orchestrator),
    openai_client=Depends(get_openai_moderation_client),
    metadata_client=Depends(get_async_openai_client),
) -> EstimationResponse:
    """Genera estimación multi-turno en sesión y soporta adjuntos opcionales."""
    files = files or []
    if files and not settings.attachments_enabled:
        raise HTTPException(status_code=400, detail="Attachments are disabled")
    if len(files) > settings.attachments_max_files:
        raise HTTPException(
            status_code=422,
            detail=f"Too many attachments (max={settings.attachments_max_files})",
        )

    extracted: list[tuple[str, str]] = []
    max_file_size_bytes = settings.attachments_max_file_size_mb * 1024 * 1024
    for upload in files:
        filename = upload.filename or "attachment"
        content = await upload.read()
        if len(content) > max_file_size_bytes:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Attachment {filename!r} exceeds "
                    f"{settings.attachments_max_file_size_mb} MB"
                ),
            )
        try:
            text = extract_text(
                filename=filename,
                content=content,
                max_chars=settings.attachments_max_chars_per_file,
            )
        except UnsupportedAttachmentError as exc:
            raise HTTPException(status_code=415, detail=exc.message) from exc
        except AttachmentExtractionError as exc:
            raise HTTPException(status_code=422, detail=exc.message) from exc
        if text:
            extracted.append((filename, text))

    enriched_description = enrich_transcript(
        transcript=description,
        attachments=extracted,
    )
    try:
        request = EstimationRequest(
            description=enriched_description,
            project_type=project_type,
            detail_level=detail_level,
            session_id=session_id,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    return await run_estimation_pipeline(
        request=request,
        settings=settings,
        wrapper=wrapper,
        orchestrator=orchestrator,
        openai_client=openai_client,
        metadata_client=metadata_client,
    )
