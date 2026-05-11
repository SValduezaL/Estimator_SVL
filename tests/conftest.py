"""Fixtures de pytest para la API."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.context.examples import CANONICAL_EXAMPLES
from app.main import app


def _test_settings() -> Settings:
    return Settings(
        openai_api_key="sk-test-pytest",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_models_by_provider={
            "openai": ["gpt-4o-mini", "gpt-4o"],
            "anthropic": ["claude-haiku-4-5"],
        },
    )


@pytest.fixture
def test_settings() -> Settings:
    return _test_settings()


@pytest.fixture
def litellm_stub_log(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Sustituye LiteLLM/Router por dobles que registran kwargs y devuelven respuesta fija."""
    log: list[dict] = []
    est_md = CANONICAL_EXAMPLES[0].estimation_markdown

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
        msg = type("M", (), {"content": est_md})()
        choice = type("C", (), {"finish_reason": finish_reason, "message": msg})()
        return type("R", (), {"choices": [choice], "usage": usage, "model": "gpt-4o-mini"})()

    def _stream_chunks() -> Iterator[object]:
        d1 = type("D1", (), {"content": "stream-chunk"})()
        ch1 = type("Ch1", (), {"delta": d1})()
        c1 = type("C1", (), {"choices": [ch1], "usage": None})()
        yield c1
        d2 = type("D2", (), {"content": None})()
        ch2 = type("Ch2", (), {"delta": d2})()
        usage = type(
            "Us",
            (),
            {
                "prompt_tokens": 2,
                "completion_tokens": 2,
                "total_tokens": 4,
            },
        )()
        c2 = type("C2", (), {"choices": [ch2], "usage": usage})()
        yield c2

    import app.services.llm_wrapper as lw_mod

    class FakeRouter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def completion(self, model: str, **kwargs: object) -> object:
            log.append({"source": "router", "route_model": model, **kwargs})
            if kwargs.get("stream"):
                return _stream_chunks()
            max_t = int(kwargs.get("max_tokens") or 4000)
            fr = "length" if max_t <= 200 else "stop"
            return make_response(fr)

    monkeypatch.setattr(lw_mod, "Router", FakeRouter)

    def litellm_completion(**kwargs: object) -> object:
        log.append({"source": "litellm", **kwargs})
        if kwargs.get("stream"):
            return _stream_chunks()
        max_t = int(kwargs.get("max_tokens") or 4000)
        fr = "length" if max_t <= 200 else "stop"
        return make_response(fr)

    monkeypatch.setattr(lw_mod.litellm, "completion", litellm_completion)
    return log


@pytest.fixture
def client(test_settings: Settings, litellm_stub_log: list[dict]) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield TestClient(app)
    app.dependency_overrides.clear()
