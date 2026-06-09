from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.foundation.observability.config import configure_logging
from app.foundation.observability.exceptions import register_exception_handlers
from app.foundation.observability.middleware import RequestContextMiddleware
from app.api import config, embeddings, estimations, sessions


APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings, version=APP_VERSION)
    yield


app = FastAPI(
    title=f"{settings.app_name} - Proyecto 1",
    version=APP_VERSION,
    description=(
        "Servicio FastAPI para generar estimaciones de software desde descripciones "
        "estructuradas (tipo de proyecto, nivel de detalle) con salida JSON tipada "
        "(EstimationResult vía Instructor + LiteLLM) y arquitectura CAG."
    ),
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)

app.include_router(estimations.router)
app.include_router(sessions.router)
app.include_router(embeddings.router)
app.include_router(config.router)


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
