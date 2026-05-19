"""Exception handlers FastAPI con logging estructurado."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

log = structlog.get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
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
