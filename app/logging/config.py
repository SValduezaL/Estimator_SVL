"""Configuración central de structlog y puente stdlib."""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import Processor

from app.config import Settings
from app.logging.processors import (
    add_otel_context,
    add_service_context,
    redact_sensitive,
    set_service_metadata,
)


def _shared_processors() -> list[Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        add_otel_context,
        add_service_context,
        redact_sensitive,
        structlog.processors.format_exc_info,
    ]


def configure_logging(settings: Settings, *, version: str = "0.1.0") -> None:
    """Configura structlog + logging stdlib según ``app_env`` y ``log_level``."""
    json_logs = settings.app_env in ("staging", "prod")
    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )

    set_service_metadata(
        service=settings.app_name,
        app_env=settings.app_env,
        version=version,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *_shared_processors(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_shared_processors(),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    for name in ("uvicorn", "uvicorn.error", "app"):
        logging.getLogger(name).setLevel(settings.log_level)
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING if json_logs else logging.INFO
    )
    for noisy in ("httpx", "httpcore", "openai", "litellm"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
