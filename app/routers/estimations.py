"""Router HTTP para estimaciones."""

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.estimation import EstimationRequest, EstimationResponse
from app.services.llm_service import generate_estimation

router = APIRouter(prefix="/api/v1", tags=["estimations"])


@router.post("/estimate", response_model=EstimationResponse)
async def estimate(
    request: EstimationRequest,
    settings: Settings = Depends(get_settings),
) -> EstimationResponse:
    """Recibe una transcripcion y delega la estimacion al servicio."""
    return await generate_estimation(request.transcription, settings=settings)
