from fastapi import FastAPI

from app.config import settings
from app.routers import estimations


APP_VERSION = "0.1.0"


app = FastAPI(
    title=f"{settings.app_name} - Proyecto 1",
    version=APP_VERSION,
    description=(
        "Servicio FastAPI para generar estimaciones de software desde descripciones "
        "estructuradas (tipo de proyecto, nivel de detalle, formato de salida) usando "
        "arquitectura CAG (contexto estático inyectado en prompt), con respuesta JSON."
    ),
)

app.include_router(estimations.router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": APP_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/version", tags=["meta"])
async def version_info() -> dict[str, str]:
    return {"version": APP_VERSION}


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/ready", tags=["health"])
async def ready() -> dict[str, object]:
    return {
        "status": "ready",
        "checks": {},
        "note": "stub: aún no valida dependencias (LLM provider, claves, etc.)",
    }
