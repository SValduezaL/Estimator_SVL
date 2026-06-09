import json
from typing import Any, Literal
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.foundation.llm.pricing import provider_from_model


class Settings(BaseSettings):
    app_name: str = Field(default="Estimador CAG API", min_length=3)
    app_env: Literal["dev", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    
    # LLM
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
    max_tokens: int = Field(default=2000, ge=100, le=4000)
    
    # Fallback LiteLLM (opcional): segundo despliegue bajo el mismo route ``estimator``.
    llm_fallback_model: str | None = Field(default="claude-haiku-4-5-20251001")
    llm_timeout_seconds: int = Field(default=30, ge=5, le=600)
    llm_num_retries: int = Field(default=2, ge=0, le=10)
    
    # Caché Redis (opcional): vacío = sin caché; p. ej. redis://redis:6379/0 en Compose
    redis_url: str | None = Field(default=None)
    cache_ttl_seconds: int = Field(default=86400, ge=60, le=604800)

    # Caché semántica (Redis Stack + embeddings; requiere RediSearch)
    semantic_cache_enabled: bool = Field(default=False)
    semantic_cache_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    semantic_cache_log_only: bool = Field(default=False)
    semantic_cache_ttl_seconds: int | None = Field(default=86400, ge=60, le=604800)
    semantic_cache_max_results: int = Field(default=3, ge=1, le=20)
    semantic_cache_index_name: str = Field(default="estimations_v1")
    semantic_cache_key_prefix: str = Field(default="estimation:semantic:v1")
    semantic_embedding_provider: str = Field(default="openai")
    semantic_embedding_model: str = Field(default="text-embedding-3-small")
    semantic_embedding_dimensions: int = Field(default=1536, ge=1, le=4096)

    # Guardrails (defense-in-depth)
    guardrails_enabled: bool = Field(default=True)
    guardrails_moderation_enabled: bool = Field(default=True)
    guardrails_injection_enabled: bool = Field(default=True)
    guardrails_pii_input_enabled: bool = Field(default=True)
    guardrails_pii_output_enabled: bool = Field(default=True)
    guardrails_output_semantic_enabled: bool = Field(default=True)
    guardrails_moderation_log_only: bool = Field(default=False)
    guardrails_injection_log_only: bool = Field(default=False)
    guardrails_pii_input_log_only: bool = Field(default=False)
    guardrails_moderation_model: str = Field(default="omni-moderation-latest")
    guardrails_moderation_thresholds: dict[str, float] = Field(default_factory=dict)
    guardrails_injection_pattern_version: str = Field(default="v1")
    guardrails_fail_open_on_moderation_error: bool = Field(default=True)
    guardrails_output_max_retries: int = Field(default=1, ge=0, le=5)
    guardrails_judge_enabled: bool = Field(default=False)
    guardrails_min_eur_per_hour: float = Field(default=20.0, ge=1.0, le=500.0)
    guardrails_max_eur_per_hour: float = Field(default=250.0, ge=1.0, le=2000.0)
    guardrails_hours_per_week: int = Field(default=40, ge=1, le=80)
    guardrails_prompt_max_chars: int = Field(default=120_000, ge=10_000, le=500_000)
    
    # Attachments
    attachments_enabled: bool = Field(default=True)
    attachments_max_files: int = Field(default=5, ge=1, le=20)
    attachments_max_file_size_mb: int = Field(default=10, ge=1, le=100)
    attachments_max_chars_per_file: int = Field(default=12_000, ge=500, le=200_000)
    
    # Memory
    memory_anchors_enabled: bool = Field(default=True)
    memory_anchors_max_items: int = Field(default=20, ge=1, le=200)
    memory_summary_enabled: bool = Field(default=True)
    memory_summary_max_chars: int = Field(default=4000, ge=200, le=20000)
    memory_summary_model: str = Field(default="gpt-4o-mini")
    memory_summary_timeout_seconds: int = Field(default=60, ge=5, le=300)
    memory_summary_max_retries: int = Field(default=1, ge=0, le=5)
    
    # Tier Rules
    tier_rules_enabled: bool = Field(default=True)

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

    @field_validator("guardrails_moderation_thresholds", mode="before")
    @classmethod
    def parse_moderation_thresholds(cls, value: Any) -> dict[str, float]:
        if value is None or value == "":
            return {}
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise ValueError("GUARDRAILS_MODERATION_THRESHOLDS debe ser un JSON object.")
        return {str(k): float(v) for k, v in value.items()}

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

    def resolved_semantic_cache_ttl(self) -> int:
        if self.semantic_cache_ttl_seconds is not None:
            return int(self.semantic_cache_ttl_seconds)
        return int(self.cache_ttl_seconds)

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

        if self.llm_fallback_model:
            for mid in (self.llm_model, self.llm_fallback_model):
                prov = provider_from_model(mid)
                if prov == "openai" and not self.openai_api_key:
                    raise ValueError(
                        "LLM_FALLBACK_MODEL requiere OPENAI_API_KEY cuando el modelo "
                        f"o el fallback usan OpenAI ({mid!r})."
                    )
                if prov == "anthropic" and not self.anthropic_api_key:
                    raise ValueError(
                        "LLM_FALLBACK_MODEL requiere ANTHROPIC_API_KEY cuando el modelo "
                        f"o el fallback usan Anthropic ({mid!r})."
                    )
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
