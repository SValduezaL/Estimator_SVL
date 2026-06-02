"""Configuración structlog mínima para ai_service."""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import Processor

from ai_service.app.config import Settings


def configure_logging(settings: Settings, *, version: str = "0.1.0") -> None:
    json_logs = settings.app_env in ("staging", "prod")
    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )

    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    if json_logs:
        shared.append(structlog.processors.format_exc_info)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
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

    for name in ("uvicorn", "uvicorn.error", "ai_service"):
        logging.getLogger(name).setLevel(settings.log_level)

    structlog.get_logger(__name__).info(
        "logging_configured",
        service=settings.app_name,
        app_env=settings.app_env,
        version=version,
    )
