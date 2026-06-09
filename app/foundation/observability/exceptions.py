"""Exception handlers FastAPI con logging estructurado."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.config import get_settings
from app.foundation.guardrails.exceptions import GuardrailBlocked, InputGuardrailViolation

log = structlog.get_logger(__name__)

_INPUT_REASON_MESSAGES = {
    "moderation": "Content not allowed by moderation policy.",
    "prompt_injection": "Suspicious instruction-like content detected.",
    "pii": "Personal or sensitive data detected in description.",
}


def _input_guardrail_client_detail(exc: InputGuardrailViolation) -> str:
    settings = get_settings()
    if settings.app_env == "dev":
        return exc.message
    return _INPUT_REASON_MESSAGES.get(exc.reason, "Request could not be processed.")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InputGuardrailViolation)
    async def input_guardrail_handler(
        request: Request,
        exc: InputGuardrailViolation,
    ) -> JSONResponse:
        log.warning(
            "input_guardrail_blocked",
            log_category="guardrails",
            reason=exc.reason,
            error_recoverable=True,
        )
        return JSONResponse(
            status_code=400,
            content={"detail": _input_guardrail_client_detail(exc), "reason": exc.reason},
        )

    @app.exception_handler(GuardrailBlocked)
    async def guardrail_blocked_handler(
        request: Request,
        exc: GuardrailBlocked,
    ) -> JSONResponse:
        status = 400 if exc.phase == "input" else 502
        log.warning(
            "guardrail_blocked",
            log_category="guardrails",
            phase=exc.phase,
            guardrail_name=exc.guardrail_name,
            http_status=status,
        )
        settings = get_settings()
        detail = exc.message if settings.app_env == "dev" else "Request could not be processed"
        if exc.phase == "output" and settings.app_env != "dev":
            detail = "Structured estimation failed"
        return JSONResponse(status_code=status, content={"detail": detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        log.warning(
            "request_validation_failed",
            log_category="technical",
            error_recoverable=True,
            errors=exc.errors(),
        )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        log.warning(
            "http_exception",
            log_category="technical",
            error_recoverable=True,
            http_status=exc.status_code,
            detail=exc.detail,
        )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        log.exception(
            "unhandled_exception",
            log_category="technical",
            critical=True,
            error_type=type(exc).__name__,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
