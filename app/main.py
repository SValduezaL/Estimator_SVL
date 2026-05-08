from fastapi import FastAPI

from app.config import settings
from app.routers import estimations

app = FastAPI(
    title=f"{settings.app_name} - Proyecto 1",
    version="0.1.0",
    description=(
        "Servicio FastAPI para generar estimaciones de software desde transcripciones "
        "de reuniones usando arquitectura CAG (contexto estático inyectado en prompt)."
    ),
)

app.include_router(estimations.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}
