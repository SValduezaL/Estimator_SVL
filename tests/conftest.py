"""Fixtures de pytest para la API."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import structlog
from fastapi.testclient import TestClient
from structlog.testing import CapturingLogger

from app.config import Settings, get_settings
from app.logging.config import configure_logging
from app.main import app

_LITELLM_STUB_COMPLETION_MARKDOWN = "## Estimación de prueba\n\nContenido mínimo para el doble de LiteLLM."


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
    )


@pytest.fixture(autouse=True)
def _configure_logging_for_tests() -> Iterator[None]:
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
    """Sustituye LiteLLM/Router por dobles que registran kwargs y devuelven respuesta fija."""
    log: list[dict] = []

    def make_response(finish_reason: str) -> object:
        usage = type(
            "U",
            (),
            {
                "prompt_tokens": 1234,
                "completion_tokens": 567,
                "total_tokens": 1801,
            },
        )()
        msg = type("M", (), {"content": _LITELLM_STUB_COMPLETION_MARKDOWN})()
        choice = type("C", (), {"finish_reason": finish_reason, "message": msg})()
        return type("R", (), {"choices": [choice], "usage": usage, "model": "gpt-4o-mini"})()

    import app.services.llm_wrapper as lw_mod

    class FakeRouter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def completion(self, model: str, **kwargs: object) -> object:
            log.append({"source": "router", "route_model": model, **kwargs})
            max_t = int(kwargs.get("max_tokens") or 4000)
            fr = "length" if max_t <= 200 else "stop"
            return make_response(fr)

    monkeypatch.setattr(lw_mod, "Router", FakeRouter)

    def litellm_completion(**kwargs: object) -> object:
        log.append({"source": "litellm", **kwargs})
        max_t = int(kwargs.get("max_tokens") or 4000)
        fr = "length" if max_t <= 200 else "stop"
        return make_response(fr)

    monkeypatch.setattr(lw_mod.litellm, "completion", litellm_completion)
    return log


@pytest.fixture
def client(test_settings: Settings, litellm_stub_log: list[dict]) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
