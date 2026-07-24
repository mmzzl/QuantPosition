import logging
import uuid
from datetime import datetime, timezone
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", str(uuid.uuid4()))


def _error_response(request: Request, status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "trace_id": _get_trace_id(request),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "trace_id": _get_trace_id(request),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    logger.error(f"HTTP exception: {exc}", exc_info=True)
    return _error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": str(exc.errors()),
            "trace_id": _get_trace_id(request),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return _error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")


async def service_unavailable_handler(request: Request, exc: Exception):
    logger.error(f"Service unavailable: {exc}", exc_info=True)
    return _error_response(request, status.HTTP_503_SERVICE_UNAVAILABLE, "Service unavailable")


def setup_error_handlers(app):
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
