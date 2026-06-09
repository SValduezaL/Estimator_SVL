"""Fixtures para tests de guardrails."""

from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def _clear_injection_cache() -> None:
    from app.foundation.guardrails.injection import clear_pattern_registry_cache

    clear_pattern_registry_cache()
    yield
    clear_pattern_registry_cache()


@pytest.fixture
def guardrails_strict_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_models_by_provider={"openai": ["gpt-4o-mini"]},
        app_env="dev",
        log_level="INFO",
        guardrails_enabled=True,
        guardrails_moderation_enabled=True,
        guardrails_injection_enabled=True,
        guardrails_pii_input_enabled=True,
        guardrails_pii_output_enabled=True,
        guardrails_output_semantic_enabled=True,
        guardrails_moderation_log_only=False,
        guardrails_injection_log_only=False,
        guardrails_pii_input_log_only=False,
        guardrails_fail_open_on_moderation_error=True,
    )


@pytest.fixture
def guardrails_disabled_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_models_by_provider={"openai": ["gpt-4o-mini"]},
        app_env="dev",
        log_level="INFO",
        guardrails_enabled=False,
    )
