"""Tests de configuración structlog."""

from __future__ import annotations

import json
import logging
from io import StringIO

import structlog

from app.config import Settings
from app.logging.config import configure_logging
from app.logging.processors import redact_sensitive


def _prod_settings() -> Settings:
    return Settings(
        app_env="prod",
        log_level="INFO",
        openai_api_key="sk-test",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
    )


def test_configure_logging_prod_emits_json_with_metadata() -> None:
    configure_logging(_prod_settings(), version="0.1.0-test")

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    root = logging.getLogger()
    handler.setFormatter(root.handlers[0].formatter)
    root.handlers.clear()
    root.addHandler(handler)

    log = structlog.get_logger("test_capture")
    log.info("json_line_event", log_category="technical", foo="bar")
    handler.flush()

    line = stream.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)

    assert payload["event"] == "json_line_event"
    assert payload["log_category"] == "technical"
    assert payload["app_env"] == "prod"
    assert payload["version"] == "0.1.0-test"
    assert "timestamp" in payload
    assert payload.get("service")


def test_redact_sensitive_strips_api_key_and_description() -> None:
    event = {
        "event": "leak_test",
        "api_key": "secret",
        "description": "user text",
        "safe_field": "ok",
    }
    out = redact_sensitive(None, "info", event)
    assert out["api_key"] == "[REDACTED]"
    assert out["description"] == "[REDACTED]"
    assert out["safe_field"] == "ok"
