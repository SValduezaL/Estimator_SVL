"""Fixtures de pytest para la API."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from fastapi.testclient import TestClient
from structlog.testing import CapturingLogger

from app.config import Settings, get_settings
from app.fixtures.estimation_examples import load_validated_example
from app.logging.config import configure_logging
from app.main import app
from app.schemas.estimation_common import ProjectType
from app.services import llm_wrapper as lw_mod

_STUB_RESULT = load_validated_example(ProjectType.WEB_SAAS, 1)


def _fake_raw_completion() -> object:
    usage = type(
        "U",
        (),
        {"prompt_tokens": 1234, "completion_tokens": 567, "total_tokens": 1801},
    )()
    msg = type("M", (), {"content": ""})()
    choice = type("C", (), {"finish_reason": "stop", "message": msg})()
    return type("R", (), {"choices": [choice], "usage": usage, "model": "gpt-4o-mini"})()


def _test_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test-pytest",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_models_by_provider={
            "openai": ["gpt-4o-mini", "gpt-4o"],
            "anthropic": ["claude-haiku-4-5"],
        },
        app_env="dev",
        log_level="INFO",
        guardrails_enabled=False,
    )


@pytest.fixture(autouse=True)
def _configure_logging_for_tests() -> Iterator[None]:
    from app.prompts.loader import clear_estimation_environment_cache

    clear_estimation_environment_cache()
    configure_logging(_test_settings(), version="0.1.0-test")
    yield


@pytest.fixture
def test_settings() -> Settings:
    return _test_settings()


@pytest.fixture
def capture_logs() -> Iterator[CapturingLogger]:
    """Logger en memoria para asertos sobre eventos structlog."""
    cap = CapturingLogger()
    structlog.configure(
        processors=[structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        logger_factory=lambda *_args, **_kwargs: cap,
        cache_logger_on_first_use=False,
    )
    yield cap
    configure_logging(_test_settings(), version="0.1.0-test")


@pytest.fixture
def litellm_stub_log(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Registra kwargs de ``complete_estimation`` sin llamar a Instructor."""
    log: list[dict] = []

    def fake_complete_estimation(**kwargs: Any) -> tuple[Any, Any]:
        log.append({"source": "structured", **kwargs})
        return _STUB_RESULT, _fake_raw_completion()

    monkeypatch.setattr(lw_mod, "complete_estimation", fake_complete_estimation)
    return log


@pytest.fixture
def client(test_settings: Settings, litellm_stub_log: list[dict]) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
