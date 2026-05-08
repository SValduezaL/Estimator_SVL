import json
from typing import Any, Literal
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Estimador CAG API", min_length=3)
    app_env: Literal["dev", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_models_by_provider: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "openai": ["gpt-4o-mini"],
            "anthropic": ["claude-haiku-4-5"],
        },
    )
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=800, ge=100, le=4000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("llm_models_by_provider", mode="before")
    @classmethod
    def parse_models_by_provider(cls, value: Any) -> dict[str, list[str]]:
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise ValueError("LLM_MODELS_BY_PROVIDER debe ser un JSON object.")
        normalized: dict[str, list[str]] = {}
        for provider, models in value.items():
            if not isinstance(provider, str) or not isinstance(models, list):
                raise ValueError("LLM_MODELS_BY_PROVIDER tiene formato invalido.")
            cleaned_models = [str(model).strip() for model in models if str(model).strip()]
            if not cleaned_models:
                raise ValueError(f"Proveedor '{provider}' sin modelos configurados.")
            normalized[provider.strip().lower()] = cleaned_models
        return normalized

    @model_validator(mode="after")
    def validate_llm_settings(self) -> "Settings":
        if self.llm_provider not in self.llm_models_by_provider:
            providers = ", ".join(sorted(self.llm_models_by_provider.keys()))
            raise ValueError(
                f"LLM_PROVIDER '{self.llm_provider}' no existe en LLM_MODELS_BY_PROVIDER. "
                f"Disponibles: {providers}."
            )

        allowed_models = self.llm_models_by_provider[self.llm_provider]
        if self.llm_model not in allowed_models:
            raise ValueError(
                f"LLM_MODEL '{self.llm_model}' no permitido para '{self.llm_provider}'. "
                f"Modelos validos: {allowed_models}."
            )

        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("Si LLM_PROVIDER=openai, OPENAI_API_KEY es obligatoria.")
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("Si LLM_PROVIDER=anthropic, ANTHROPIC_API_KEY es obligatoria.")
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
