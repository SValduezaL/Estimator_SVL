"""Router HTTP para estimaciones."""

from collections.abc import AsyncIterator
import json

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.schemas.estimation import EstimationRequest, EstimationResponse
from app.services.llm_service import LLMService, StreamEvent, generate_estimation

router = APIRouter(prefix="/api/v1", tags=["estimations"])


@router.post("/estimate", response_model=EstimationResponse)
async def estimate(
    request: EstimationRequest,
    settings: Settings = Depends(get_settings),
) -> EstimationResponse:
    """Recibe una transcripcion y delega la estimacion al servicio."""
    return await generate_estimation(request.transcription, settings=settings)


_STREAM_SENTINEL = object()


async def _iterate_in_threadpool(iterator: object) -> AsyncIterator[StreamEvent]:
    """Consume un iterador bloqueante sin bloquear el event loop."""
    while True:
        chunk = await run_in_threadpool(next, iterator, _STREAM_SENTINEL)
        if chunk is _STREAM_SENTINEL:
            break
        if chunk:
            yield chunk


def _format_sse(event_type: str, payload: dict[str, object]) -> str:
    """Serializa un evento SSE con JSON en data."""
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"


@router.post("/estimate/stream")
async def estimate_stream(
    request: EstimationRequest,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Devuelve la estimacion en streaming incremental."""
    service = LLMService(settings=settings)

    async def stream_generator() -> AsyncIterator[str]:
        try:
            iterator = service.stream_estimate(request.transcription)
            async for event in _iterate_in_threadpool(iterator):
                yield _format_sse(event.type, event.data)
        except Exception as exc:  # pragma: no cover - defensa endpoint stream
            yield _format_sse(
                "error",
                {
                    "message": (
                        "No pude generar la estimación en streaming. "
                        "Verifica proveedor/modelo y API key.\n\n"
                        f"Detalle: {exc}"
                    )
                },
            )

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
