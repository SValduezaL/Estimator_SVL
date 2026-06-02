"""Configuración del microservicio ai_service (independiente de app/)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings del microservicio ai_service.

    Usa prefijo ``AI_SERVICE_`` para no colisionar con ``APP_NAME`` del estimador
    en el ``.env`` compartido (p. ej. ``AI_SERVICE_APP_NAME``).
    """

    app_name: str = Field(default="AI Service - Embeddings", min_length=3)
    app_env: Literal["dev", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    # Clave compartida con el estimador; sin prefijo AI_SERVICE_.
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    model_config = SettingsConfigDict(
        env_prefix="AI_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
