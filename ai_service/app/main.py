"""Punto de entrada FastAPI del microservicio ai_service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_service.app.config import get_settings
from ai_service.app.embedding_pipeline.router import router as embeddings_router
from ai_service.app.logging import configure_logging
from ai_service.app.ssl_utils import configure_ssl_certificates

configure_ssl_certificates()

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings, version=APP_VERSION)
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    description=(
        "Microservicio IA para ingesta de presupuestos históricos: "
        "chunking estructural y embeddings OpenAI."
    ),
    lifespan=lifespan,
)

app.include_router(embeddings_router, prefix="/embeddings")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": APP_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}
